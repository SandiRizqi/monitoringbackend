#data/views.py
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from .models import AreaOfInterest
from .serializer import AreaOfInterestSerializer, AreaOfInterestGeoSerializer
from django.http import HttpResponse, HttpResponseForbidden
from rest_framework.authtoken.models import Token
from django.db import connection
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404
from .models import HotspotAlert, AreaOfInterest, DeforestationAlerts
from .serializer import HotspotAlertSerializer, HotspotAlertGeoSerializer, DeforestationAlertsSerializer
from .models import HotspotAlert, AreaOfInterest, DeforestationAlerts, DeforestationVerification
from .serializer import HotspotAlertSerializer, HotspotAlertGeoSerializer, DeforestationVerificationSerializer, DeforestationVerificationListSerializer
from datetime import date, datetime, timedelta
from dateutil.parser import parse as dateparse
import json
import logging
logger = logging.getLogger(__name__)
from django.db.models import Count, Q, Sum, Avg
from django.utils import timezone
from rest_framework import generics

from django.shortcuts import get_object_or_404
from .models import HotspotVerification, Hotspots
from .serializer import HotspotVerificationSerializer, HotspotVerificationListSerializer


class UserAOIListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        aoi_id = request.query_params.get('id')
        include_geom = request.query_params.get('geom') == 'true'

        if aoi_id:
            queryset = AreaOfInterest.objects.filter(id=aoi_id, users_aoi=user)
        else:
            queryset = AreaOfInterest.objects.filter(users_aoi=user)

        if include_geom:
            # Pakai serializer GeoJSON yang sudah ada
            serializer = AreaOfInterestSerializer(queryset, many=True, context={'request': request})
            features = []
            for obj, serialized in zip(queryset, serializer.data):
                geometry_str = serialized.get("geometry")
                try:
                    geometry = json.loads(geometry_str) if geometry_str else None
                except json.JSONDecodeError:
                    geometry = None

                # Hapus geometry dari properties agar tidak duplikat
                properties = {k: v for k, v in serialized.items() if k != "geometry"}

                features.append({
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": properties
                })

            return Response({
                "type": "FeatureCollection",
                "features": features
            })
        else:
            # Pakai serializer simple tanpa geometry atau geometry diolah beda
            serializer = AreaOfInterestSerializer(queryset, many=True)
            return Response(serializer.data)

    def post(self, request):
        user = request.user
        data = request.data
        aoi_id = data.get('id', None)

        if aoi_id:
            try:
                aoi = AreaOfInterest.objects.get(id=aoi_id)
            except AreaOfInterest.DoesNotExist:
                aoi = None

            if aoi:
                # Update existing AOI
                if not user.has_perm('data.change_areaofinterest') or user not in aoi.users_aoi.all():
                    return Response({'detail': 'You do not have permission to change this Area of Interest.'}, status=status.HTTP_403_FORBIDDEN)

                serializer = AreaOfInterestGeoSerializer(aoi, data=data, partial=True, context={'request': request})
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data)
                else:
                    # Tangani error validasi area
                    error_messages = []
                    for field, errors in serializer.errors.items():
                        if field == 'geometry':
                            error_messages.extend(errors)
                        else:
                            error_messages.append(f"{field}: {', '.join(errors)}")
                    
                    return Response({
                        'detail': error_messages[0] if error_messages else 'Validation error',
                        'errors': serializer.errors
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                # Create new AOI
                if not user.has_perm('data.add_areaofinterest'):
                    return Response({'detail': 'You do not have permission to add Area of Interest.'}, status=status.HTTP_403_FORBIDDEN)

                serializer = AreaOfInterestGeoSerializer(data=data, context={'request': request})
                if serializer.is_valid():
                    new_aoi = serializer.save()
                    new_aoi.users_aoi.add(user)
                    new_aoi.save()
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                else:
                    # Tangani error validasi area
                    error_messages = []
                    for field, errors in serializer.errors.items():
                        if field == 'geometry':
                            error_messages.extend(errors)
                        else:
                            error_messages.append(f"{field}: {', '.join(errors)}")
                    
                    return Response({
                        'detail': error_messages[0] if error_messages else 'Validation error',
                        'errors': serializer.errors
                    }, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Create new AOI
            if not user.has_perm('data.add_areaofinterest'):
                return Response({'detail': 'You do not have permission to add Area of Interest.'}, status=status.HTTP_403_FORBIDDEN)

            serializer = AreaOfInterestGeoSerializer(data=data, context={'request': request})
            if serializer.is_valid():
                new_aoi = serializer.save()
                new_aoi.users_aoi.add(user)
                new_aoi.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                # Tangani error validasi area
                error_messages = []
                for field, errors in serializer.errors.items():
                    if field == 'geometry':
                        error_messages.extend(errors)
                    else:
                        error_messages.append(f"{field}: {', '.join(errors)}")
                
                return Response({
                    'detail': error_messages[0] if error_messages else 'Validation error',
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        
    def delete(self, request):
        try:
            user = request.user
            aoi_id = request.query_params.get('id')

            if not aoi_id:
                return Response({'detail': 'AOI ID is required to delete.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                aoi = AreaOfInterest.objects.get(id=aoi_id)
            except AreaOfInterest.DoesNotExist:
                return Response({'detail': 'Area of Interest not found.'}, status=status.HTTP_404_NOT_FOUND)

            if not user.has_perm('data.delete_areaofinterest') or user not in aoi.users_aoi.all():
                return Response({'detail': 'You do not have permission to delete this Area of Interest.'}, status=status.HTTP_403_FORBIDDEN)

            aoi.delete()
            return Response({'detail': 'Area of Interest deleted successfully.'}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Unhandled error in delete AOI")
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        


class HotspotAlertAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk=None):
        user = request.user
        aoi_id = request.query_params.get("aoi_id")
        include_geom = request.query_params.get("geom", "false").lower() == "true"

        queryset = HotspotAlert.objects.filter(area_of_interest__in=AreaOfInterest.objects.filter(users_aoi=user))

        if pk:
            # Detail view
            alert = get_object_or_404(queryset, pk=pk)
            serializer = HotspotAlertGeoSerializer(alert) if include_geom else HotspotAlertSerializer(alert)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # List view
        if aoi_id:
            queryset = queryset.filter(area_of_interest_id=aoi_id)

        serializer_class = HotspotAlertGeoSerializer if include_geom else HotspotAlertSerializer
        serializer = serializer_class(queryset, many=True)

        if include_geom:
            features = []
            for obj, data in zip(queryset, serializer.data):
                geometry = data.get("hotspot_geom") or data.get("geom")
                try:
                    geometry = json.loads(geometry) if geometry else None
                except json.JSONDecodeError:
                    geometry = None
                properties = {k: v for k, v in data.items() if k != "hotspot_geom" and k != "geom"}
                features.append({
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": properties
                })
            return Response({
                "type": "FeatureCollection",
                "features": features
            })

        return Response(serializer.data, status=status.HTTP_200_OK)




class UserAreaOfInterestTileView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request, z, x, y):
        token_key = request.query_params.get('token')
        if not token_key:
            return HttpResponseForbidden("Token required")

        try:
            token_obj = Token.objects.select_related('user').get(key=token_key)
        except Token.DoesNotExist:
            return HttpResponseForbidden("Invalid token")

        user = token_obj.user
        user_id = user.id  # pakai user id untuk query

        sql = """
            WITH
            tile_bounds AS (
                SELECT ST_TileEnvelope(%s, %s, %s) AS geom
            ),
            mvtgeom AS (
                SELECT
                    aoi.id,
                    aoi.name,
                    aoi.description,
                    aoi.fill_color,
                    aoi.stroke_color,
                    aoi.stroke_width,
                    ST_AsMVTGeom(
                        ST_Transform(aoi.geometry, 3857),
                        tile_bounds.geom,
                        4096,
                        64,
                        true
                    ) AS geom
                FROM data_areaofinterest aoi
                JOIN accounts_users_areas_of_interest u ON aoi.id = u.areaofinterest_id
                CROSS JOIN tile_bounds
                WHERE u.users_id = %s
                AND ST_Intersects(ST_Transform(aoi.geometry, 3857), tile_bounds.geom)
                AND ST_IsValid(aoi.geometry)
            )
            SELECT ST_AsMVT(mvtgeom.*, 'layer', 4096, 'geom') FROM mvtgeom;
            """


        with connection.cursor() as cursor:
            cursor.execute(sql, [z, x, y, str(user_id)])
            tile = cursor.fetchone()[0]

        if tile:
            return HttpResponse(tile, content_type="application/x-protobuf")
        return HttpResponse(status=204)
    


class UserHotspotAlertTileView(APIView):
    # authentication_classes = [TokenAuthentication]
    # permission_classes = [IsAuthenticated]

    def get(self, request, z, x, y):
        token_key = request.query_params.get("token")
        if not token_key:
            return HttpResponseForbidden("Token required")

        try:
            token_obj = Token.objects.select_related("user").get(key=token_key)
        except Token.DoesNotExist:
            return HttpResponseForbidden("Invalid token")

        user_id = token_obj.user.id

        # Ambil parameter waktu
        startdate = request.query_params.get("startdate")
        enddate = request.query_params.get("enddate")
        today = request.query_params.get("today") == "true"

        # Filter waktu SQL tambahan
        time_filter_sql = ""
        time_filter_params = []

        if today:
            time_filter_sql = "AND alerts.alert_date = %s"
            time_filter_params = [date.today()]
        elif startdate and enddate:
            try:
                start = dateparse(startdate).date()
                end = dateparse(enddate).date()
                time_filter_sql = "AND alerts.alert_date BETWEEN %s AND %s"
                time_filter_params = [start, end]
            except Exception:
                return HttpResponse("Invalid startdate or enddate format. Use YYYY-MM-DD", status=400)

        # SQL utama
        sql =  f"""
                    WITH tile_bounds AS (
                        SELECT ST_TileEnvelope(%s, %s, %s) AS geom
                    ),
                    user_aoi AS (
                        SELECT areaofinterest_id
                        FROM accounts_users_areas_of_interest
                        WHERE users_id = %s
                    ),
                    mvtgeom AS (
                        SELECT
                            alerts.id,
                            alerts.alert_date,
                            alerts.category,
                            COALESCE(alerts.confidence, 0) AS confidence,
                            alerts.distance,
                            alerts.hotspot_id,
                            aois.name AS area_of_interest_name,
                            ST_AsMVTGeom(
                                ST_Transform(h.geom::geometry, 3857),
                                tile_bounds.geom,
                                4096,
                                64,
                                true
                            ) AS geom
                        FROM data_hotspotalert alerts
                        JOIN user_aoi ON alerts.area_of_interest_id = user_aoi.areaofinterest_id
                        JOIN data_hotspots h ON alerts.hotspot_id = h.id
                        JOIN data_areaofinterest aois ON alerts.area_of_interest_id = aois.id
                        CROSS JOIN tile_bounds
                        WHERE h.geom IS NOT NULL
                        AND ST_Intersects(ST_Transform(h.geom::geometry, 3857), tile_bounds.geom)
                        AND ST_IsValid(h.geom::geometry)
                        {time_filter_sql}
                    )
                    SELECT ST_AsMVT(mvtgeom.*, 'hotspot_alerts', 4096, 'geom') FROM mvtgeom;
                """


        with connection.cursor() as cursor:
            cursor.execute(sql, [z, x, y, str(user_id)] + time_filter_params)
            tile = cursor.fetchone()[0]

        if tile:
            return HttpResponse(tile, content_type="application/x-protobuf")
        return HttpResponse(status=204)

    


class UserDeforestationTileView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request, z, x, y):
        token_key = request.query_params.get('token')
        if not token_key:
            return HttpResponseForbidden("Token required")

        try:
            token_obj = Token.objects.select_related('user').get(key=token_key)
        except Token.DoesNotExist:
            return HttpResponseForbidden("Invalid token")

        user = token_obj.user
        user_id = user.id

        sql = """
            WITH tile_bounds AS (
                SELECT ST_TileEnvelope(%s, %s, %s) AS geom
            ),
            user_aoi AS (
                SELECT areaofinterest_id
                FROM accounts_users_areas_of_interest
                WHERE users_id = %s
            ),
            mvtgeom AS (
                SELECT
                    alerts.id,
                    alerts.event_id,
                    alerts.alert_date,
                    alerts.confidence,
                    alerts.area,
                    alerts.company_id,
                    ST_AsMVTGeom(
                        ST_Transform(alerts.geom::geometry, 3857),
                        tile_bounds.geom,
                        4096,
                        64,
                        true
                    ) AS geom
                FROM data_deforestationalerts alerts
                JOIN user_aoi ON alerts.company_id = user_aoi.areaofinterest_id
                CROSS JOIN tile_bounds
                WHERE alerts.geom IS NOT NULL
                AND ST_Intersects(ST_Transform(alerts.geom::geometry, 3857), tile_bounds.geom)
                AND ST_IsValid(alerts.geom::geometry)
            )
            SELECT ST_AsMVT(mvtgeom.*, 'deforestation_alerts', 4096, 'geom') FROM mvtgeom;
        """

        with connection.cursor() as cursor:
            cursor.execute(sql, [z, x, y, str(user_id)])
            tile = cursor.fetchone()[0]

        if tile:
            return HttpResponse(tile, content_type="application/x-protobuf")
        return HttpResponse(status=204)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def hotspot_chart_data(request):
    """API untuk ChartHotspot.tsx - data chart bulanan"""
    user = request.user
    
    # Ambil parameter tanggal dari request
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    # Set default jika tidak ada parameter
    if not start_date or not end_date:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=365)
    else:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

    # Query hotspot alerts per bulan untuk user dengan filter tanggal
    monthly_data = []
    current_date = start_date
    while current_date <= end_date:
        month_start = current_date.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        if month_end > end_date:
            month_end = end_date
            
        count = HotspotAlert.objects.filter(
            area_of_interest__users_aoi=user,
            alert_date__range=[month_start, month_end]
        ).count()
        
        monthly_data.append({
            'name': month_start.strftime('%b %Y'),
            'value': count,
            'amt': count * 100
        })
        
        # Move to next month
        if month_start.month == 12:
            current_date = month_start.replace(year=month_start.year + 1, month=1)
        else:
            current_date = month_start.replace(month=month_start.month + 1)

    # Data pie chart berdasarkan kategori dengan filter tanggal
    pie_data = []
    categories = ['AMAN', 'PERHATIAN', 'WASPADA', 'BAHAYA']
    for category in categories:
        count = HotspotAlert.objects.filter(
            area_of_interest__users_aoi=user,
            category=category,
            alert_date__range=[start_date, end_date]
        ).count()
        pie_data.append({
            'name': category,
            'value': count
        })

    return Response({
        'monthly_data': monthly_data,
        'pie_data': pie_data
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def company_table_data(request):
    """API untuk CompanyTable.tsx - data tabel perusahaan dengan detail kategori"""
    user = request.user
    
    # Ambil parameter tanggal
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    if not start_date or not end_date:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=365)
    else:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

    # Agregasi jumlah events per AOI/company dengan detail kategori
    companies = AreaOfInterest.objects.filter(users_aoi=user)
    
    company_data = []
    for company in companies:
        # Hitung total events dalam rentang tanggal
        total_events = HotspotAlert.objects.filter(
            area_of_interest=company,
            alert_date__range=[start_date, end_date]
        ).count()
        
        if total_events > 0:  # Hanya tampilkan yang ada events
            # Hitung per kategori
            aman = HotspotAlert.objects.filter(
                area_of_interest=company,
                category='AMAN',
                alert_date__range=[start_date, end_date]
            ).count()
            
            perhatian = HotspotAlert.objects.filter(
                area_of_interest=company,
                category='PERHATIAN',
                alert_date__range=[start_date, end_date]
            ).count()
            
            waspada = HotspotAlert.objects.filter(
                area_of_interest=company,
                category='WASPADA',
                alert_date__range=[start_date, end_date]
            ).count()
            
            bahaya = HotspotAlert.objects.filter(
                area_of_interest=company,
                category='BAHAYA',
                alert_date__range=[start_date, end_date]
            ).count()
            
            company_data.append({
                'name': company.name,
                'total_events': total_events,
                'aman': aman,
                'perhatian': perhatian,
                'waspada': waspada,
                'bahaya': bahaya
            })
    
    # Sort by total events
    company_data.sort(key=lambda x: x['total_events'], reverse=True)
    
    return Response(company_data[:10])  # top 10

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def event_list_data(request):
    """API untuk EventList.tsx - daftar alert terbaru dengan pagination"""
    user = request.user
    
    # Ambil parameter tanggal dan pagination
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 10))
    
    if not start_date or not end_date:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)  # Default 30 hari terakhir
    else:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

    # Query dengan filter tanggal
    queryset = HotspotAlert.objects.filter(
        area_of_interest__users_aoi=user,
        alert_date__range=[start_date, end_date]
    ).select_related('area_of_interest', 'hotspot').order_by('-alert_date', '-id')
    
    # Hitung total dan pagination
    total_count = queryset.count()
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    
    recent_alerts = queryset[start_index:end_index]
    
    events_data = []
    for alert in recent_alerts:
        events_data.append({
            'company': alert.area_of_interest.name,
            'date': alert.alert_date.strftime('%Y-%m-%d'),
            'time': alert.hotspot.times.strftime('%H:%M') if alert.hotspot.times else '00:00',
            'distance': f"{alert.distance:.2f}" if alert.distance else "0.00",
            'satellite': alert.hotspot.sat if alert.hotspot.sat else 'Unknown',
            'category': alert.get_category_display(),
            'hotspot_id': alert.hotspot.id,
            'aoi_id': alert.area_of_interest.id
        })

    return Response({
        'data': events_data,
        'pagination': {
            'current_page': page,
            'page_size': page_size,
            'total_count': total_count,
            'total_pages': (total_count + page_size - 1) // page_size,
            'has_next': end_index < total_count,
            'has_previous': page > 1
        }
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def hotspot_stats_data(request):
    """API untuk HotspotStats.tsx - statistik hotspot dengan filter tanggal"""
    user = request.user
    
    # Ambil parameter tanggal
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    if not start_date or not end_date:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=365)
    else:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

    # Total kejadian dengan filter tanggal
    total_events = HotspotAlert.objects.filter(
        area_of_interest__users_aoi=user,
        alert_date__range=[start_date, end_date]
    ).count()

    # Total area (jumlah AOI unik yang punya alert dalam rentang tanggal)
    total_areas = AreaOfInterest.objects.filter(
        users_aoi=user,
        hotspot_alerts__alert_date__range=[start_date, end_date]
    ).distinct().count()

    # Jumlah PT/AOI yang terlibat
    total_companies = AreaOfInterest.objects.filter(
        users_aoi=user
    ).count()

    return Response({
        'total_events': total_events,
        'total_areas': total_areas,
        'total_companies': total_companies
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def deforestation_chart_data(request):
    """API untuk ChartDeforestation.tsx - data chart bulanan deforestation"""
    user = request.user
    
    # Ambil parameter tanggal dari request
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    # Set default jika tidak ada parameter
    if not start_date or not end_date:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=365)
    else:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
    
    # Query deforestation alerts per bulan untuk user dengan filter tanggal
    monthly_data = []
    current_date = start_date
    
    while current_date <= end_date:
        month_start = current_date.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        if month_end > end_date:
            month_end = end_date
        
        count = DeforestationAlerts.objects.filter(
            company__users_aoi=user,
            alert_date__range=[month_start, month_end]
        ).count()
        
        monthly_data.append({
            'name': month_start.strftime('%b %Y'),
            'value': count,
            'amt': count * 100
        })
        
        # Move to next month
        if month_start.month == 12:
            current_date = month_start.replace(year=month_start.year + 1, month=1)
        else:
            current_date = month_start.replace(month=month_start.month + 1)
    
    # Data pie chart berdasarkan confidence level
    pie_data = []
    confidence_ranges = [
        {'name': 'Low (0-2)', 'min': 0, 'max': 2},
        {'name': 'Medium (3-4)', 'min': 3, 'max': 4},
        {'name': 'High (5+)', 'min': 5, 'max': 100}
    ]
    
    for range_data in confidence_ranges:
        count = DeforestationAlerts.objects.filter(
            company__users_aoi=user,
            confidence__range=[range_data['min'], range_data['max']],
            alert_date__range=[start_date, end_date]
        ).count()
        
        pie_data.append({
            'name': range_data['name'],
            'value': count
        })
    
    return Response({
        'monthly_data': monthly_data,
        'pie_data': pie_data
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def deforestation_company_table_data(request):
    """API untuk CompanyTable.tsx - data tabel perusahaan dengan detail deforestation"""
    user = request.user
    
    # Ambil parameter tanggal
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    if not start_date or not end_date:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=365)
    else:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
    
    # Agregasi jumlah events per AOI/company
    companies = AreaOfInterest.objects.filter(users_aoi=user)
    company_data = []
    
    for company in companies:
        # Hitung total events dalam rentang tanggal
        total_events = DeforestationAlerts.objects.filter(
            company=company,
            alert_date__range=[start_date, end_date]
        ).count()
        
        if total_events > 0:  # Hanya tampilkan yang ada events
            # Hitung total area yang terdeforestasi
            total_area = DeforestationAlerts.objects.filter(
                company=company,
                alert_date__range=[start_date, end_date]
            ).aggregate(total=Sum('area'))['total'] or 0
            
            # Hitung rata-rata confidence
            avg_confidence = DeforestationAlerts.objects.filter(
                company=company,
                alert_date__range=[start_date, end_date]
            ).aggregate(avg=Avg('confidence'))['avg'] or 0
            
            company_data.append({
                'name': company.name,
                'total_events': total_events,
                'total_area': float(total_area),
                'avg_confidence': round(float(avg_confidence), 2)
            })
    
    # Sort by total events
    company_data.sort(key=lambda x: x['total_events'], reverse=True)
    
    return Response(company_data[:10])  # top 10

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def deforestation_event_list_data(request):
    """API untuk EventList.tsx - daftar deforestation alerts terbaru dengan pagination"""
    user = request.user
    
    # Ambil parameter tanggal dan pagination
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 10))
    
    if not start_date or not end_date:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)  # Default 30 hari terakhir
    else:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
    
    # Query dengan filter tanggal
    queryset = DeforestationAlerts.objects.filter(
        company__users_aoi=user,
        alert_date__range=[start_date, end_date]
    ).select_related('company').order_by('-alert_date', '-id')
    
    # Hitung total dan pagination
    total_count = queryset.count()
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    recent_alerts = queryset[start_index:end_index]
    
    events_data = []
    for alert in recent_alerts:
        events_data.append({
            'company': alert.company.name,
            'date': alert.alert_date.strftime('%Y-%m-%d'),
            'area': f"{alert.area:.2f}" if alert.area else "0.00",
            'confidence': alert.confidence or 0,
            'event_id': alert.event_id,
            'aoi_id': alert.company.id
        })
    
    return Response({
        'data': events_data,
        'pagination': {
            'current_page': page,
            'page_size': page_size,
            'total_count': total_count,
            'total_pages': (total_count + page_size - 1) // page_size,
            'has_next': end_index < total_count,
            'has_previous': page > 1
        }
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def deforestation_stats_data(request):
    """API untuk DeforestationStats.tsx - statistik deforestation dengan filter tanggal"""
    user = request.user
    
    # Ambil parameter tanggal
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    if not start_date or not end_date:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=365)
    else:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
    
    # Total kejadian dengan filter tanggal
    total_events = DeforestationAlerts.objects.filter(
        company__users_aoi=user,
        alert_date__range=[start_date, end_date]
    ).count()
    
    # Total area yang terdeforestasi
    total_area = DeforestationAlerts.objects.filter(
        company__users_aoi=user,
        alert_date__range=[start_date, end_date]
    ).aggregate(total=Sum('area'))['total'] or 0
    
    # Total PT/AOI yang terlibat
    total_companies = AreaOfInterest.objects.filter(
        users_aoi=user,
        deforestation_alerts__alert_date__range=[start_date, end_date]
    ).distinct().count()
    
    return Response({
        'total_events': total_events,
        'total_area': float(total_area),
        'total_companies': total_companies
    })



class DeforestationAlertDetailView(generics.RetrieveAPIView):
    queryset = DeforestationAlerts.objects.all()
    serializer_class = DeforestationAlertsSerializer
    lookup_field = 'id'

    
class DeforestationVerificationAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, pk=None):
        user = request.user
        
        if pk:
            # Detail view - ambil satu verifikasi
            verification = get_object_or_404(
                DeforestationVerification.objects.select_related('alert', 'alert__company', 'verifier'),
                pk=pk,
                alert__company__users_aoi=user
            )
            serializer = DeforestationVerificationSerializer(verification)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        # List view - ambil semua verifikasi user
        queryset = DeforestationVerification.objects.filter(
            alert__company__users_aoi=user
        ).select_related('alert', 'alert__company', 'verifier').order_by('-verification_date')
        
        serializer = DeforestationVerificationListSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request):
        user = request.user
        data = request.data.copy()
        
        # Validasi bahwa alert_id ada dan user memiliki akses
        alert_id = data.get('alert')
        if not alert_id:
            return Response(
                {'detail': 'Alert ID is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            alert = DeforestationAlerts.objects.get(
                id=alert_id,
                company__users_aoi=user
            )
        except DeforestationAlerts.DoesNotExist:
            return Response(
                {'detail': 'Deforestation alert not found or access denied'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Cek apakah sudah ada verifikasi untuk alert ini
        existing_verification = DeforestationVerification.objects.filter(alert=alert).first()
        if existing_verification:
            return Response(
                {'detail': 'Verification already exists for this alert'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = DeforestationVerificationSerializer(
            data=data, 
            context={'request': request}
        )
        
        if serializer.is_valid():
            verification = serializer.save()
            return Response(
                DeforestationVerificationSerializer(verification).data, 
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def put(self, request, pk):
        user = request.user
        
        try:
            verification = DeforestationVerification.objects.get(
                pk=pk,
                alert__company__users_aoi=user
            )
        except DeforestationVerification.DoesNotExist:
            return Response(
                {'detail': 'Verification not found or access denied'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = DeforestationVerificationSerializer(
            verification, 
            data=request.data, 
            context={'request': request},
            partial=True
        )
        
        if serializer.is_valid():
            verification = serializer.save()
            return Response(
                DeforestationVerificationSerializer(verification).data,
                status=status.HTTP_200_OK
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        user = request.user
        
        try:
            verification = DeforestationVerification.objects.get(
                pk=pk,
                alert__company__users_aoi=user
            )
        except DeforestationVerification.DoesNotExist:
            return Response(
                {'detail': 'Verification not found or access denied'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        verification.delete()
        return Response(
            {'detail': 'Verification deleted successfully'}, 
            status=status.HTTP_200_OK
        )


class HotspotVerificationAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk=None):
        user = request.user
        
        if pk:
            # Detail view - ambil satu verifikasi
            verification = get_object_or_404(
                HotspotVerification.objects.select_related('hotspot', 'verifier'),
                pk=pk,
                verifier=user
            )
            serializer = HotspotVerificationSerializer(verification)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        # List view - ambil semua verifikasi user
        queryset = HotspotVerification.objects.filter(
            verifier=user
        ).select_related('hotspot', 'verifier').order_by('-verification_date')
        
        serializer = HotspotVerificationListSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        user = request.user
        data = request.data.copy()
        
        # Validasi bahwa hotspot_id ada
        hotspot_id = data.get('hotspot')
        if not hotspot_id:
            return Response(
                {'detail': 'Hotspot ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            hotspot = Hotspots.objects.get(id=hotspot_id)
        except Hotspots.DoesNotExist:
            return Response(
                {'detail': 'Hotspot not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Cek apakah sudah ada verifikasi untuk hotspot ini oleh user yang sama
        existing_verification = HotspotVerification.objects.filter(
            hotspot=hotspot, 
            verifier=user
        ).first()
        
        if existing_verification:
            return Response(
                {'detail': 'Verification already exists for this hotspot by this user'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = HotspotVerificationSerializer(
            data=data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            verification = serializer.save()
            return Response(
                HotspotVerificationSerializer(verification).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        user = request.user
        
        try:
            verification = HotspotVerification.objects.get(
                pk=pk,
                verifier=user
            )
        except HotspotVerification.DoesNotExist:
            return Response(
                {'detail': 'Verification not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = HotspotVerificationSerializer(
            verification,
            data=request.data,
            context={'request': request},
            partial=True
        )
        
        if serializer.is_valid():
            verification = serializer.save()
            return Response(
                HotspotVerificationSerializer(verification).data,
                status=status.HTTP_200_OK
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        user = request.user
        
        try:
            verification = HotspotVerification.objects.get(
                pk=pk,
                verifier=user
            )
        except HotspotVerification.DoesNotExist:
            return Response(
                {'detail': 'Verification not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        verification.delete()
        return Response(
            {'detail': 'Verification deleted successfully'},
            status=status.HTTP_200_OK
        )

