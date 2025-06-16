from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import AreaOfInterest
from .serializer import AreaOfInterestSerializer, AreaOfInterestGeoSerializer
from django.http import HttpResponse, HttpResponseForbidden
from rest_framework.authtoken.models import Token
from django.db import connection
# from django.shortcuts import get_object_or_404
import json
import logging
logger = logging.getLogger(__name__)

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
        # print(data)

        if aoi_id:
            try:
                aoi = AreaOfInterest.objects.get(id=aoi_id)
            except AreaOfInterest.DoesNotExist:
                # Jika id dikirim tapi tidak ada di DB, anggap create baru
                aoi = None

            if aoi:
                # Cek apakah user punya akses ke AOI ini dan permission change
                if not user.has_perm('data.change_areaofinterest') or user not in aoi.users_aoi.all():
                    return Response({'detail': 'You do not have permission to change this Area of Interest.'}, status=status.HTTP_403_FORBIDDEN)

                serializer = AreaOfInterestGeoSerializer(aoi, data=data, partial=True, context={'request': request})
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            else:
                # AOI tidak ada, lanjut ke create baru
                if not user.has_perm('data.add_areaofinterest'):
                    return Response({'detail': 'You do not have permission to add Area of Interest.'}, status=status.HTTP_403_FORBIDDEN)
                
                serializer = AreaOfInterestGeoSerializer(data=data, context={'request': request})
                if serializer.is_valid():
                    new_aoi = serializer.save()
                    new_aoi.users_aoi.add(user)
                    new_aoi.save()
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Tidak ada id, buat baru
            if not user.has_perm('data.add_areaofinterest'):
                return Response({'detail': 'You do not have permission to add Area of Interest.'}, status=status.HTTP_403_FORBIDDEN)
            
            serializer = AreaOfInterestGeoSerializer(data=data, context={'request': request})
            if serializer.is_valid():
                new_aoi = serializer.save()
                new_aoi.users_aoi.add(user)
                new_aoi.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
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
    # Anda bisa aktifkan permission jika sudah setup DRF auth:
    # authentication_classes = [TokenAuthentication]
    # permission_classes = [IsAuthenticated]

    def get(self, request, z, x, y):
        token_key = request.query_params.get('token')
        if not token_key:
            return HttpResponseForbidden("Token required")

        try:
            token_obj = Token.objects.select_related('user').get(key=token_key)
        except Token.DoesNotExist:
            return HttpResponseForbidden("Invalid token")

        user_id = token_obj.user.id

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
                            alerts.alert_date,
                            alerts.category,
                            COALESCE(alerts.confidence, 0) AS confidence,
                            alerts.distance,
                            alerts.area_of_interest_id,
                            alerts.hotspot_id,
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
                        CROSS JOIN tile_bounds
                        WHERE h.geom IS NOT NULL
                        AND ST_Intersects(ST_Transform(h.geom::geometry, 3857), tile_bounds.geom)
                        AND ST_IsValid(h.geom::geometry)
                    )
                    SELECT ST_AsMVT(mvtgeom.*, 'hotspot_alerts', 4096, 'geom') FROM mvtgeom;
                """


        with connection.cursor() as cursor:
            cursor.execute(sql, [z, x, y, str(user_id)])
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
    
