from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import AreaOfInterest
from .serializer import AreaOfInterestSerializer
from django.shortcuts import get_object_or_404
import json

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

        serializer = AreaOfInterestSerializer(queryset, many=True, context={'request': request})

        if include_geom:
            features = []
            for obj, serialized in zip(queryset, serializer.data):
                geometry_str = serialized.get("geometry")
                try:
                    geometry = json.loads(geometry_str) if geometry_str else None
                except json.JSONDecodeError:
                    geometry = None

                # Remove the 'geometry' from properties (to avoid duplication)
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

        return Response(serializer.data)

    def post(self, request):
        user = request.user
        data = request.data
        aoi_id = data.get('id', None)

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

                serializer = AreaOfInterestSerializer(aoi, data=data, partial=True, context={'request': request})
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            else:
                # AOI tidak ada, lanjut ke create baru
                if not user.has_perm('data.add_areaofinterest'):
                    return Response({'detail': 'You do not have permission to add Area of Interest.'}, status=status.HTTP_403_FORBIDDEN)
                
                serializer = AreaOfInterestSerializer(data=data, context={'request': request})
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
            
            serializer = AreaOfInterestSerializer(data=data, context={'request': request})
            if serializer.is_valid():
                new_aoi = serializer.save()
                new_aoi.users_aoi.add(user)
                new_aoi.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
