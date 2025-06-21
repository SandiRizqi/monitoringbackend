#accounts/views.py
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate
from .models import Users
from rest_framework import status
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.models import Token


@api_view(['POST'])
def save_google_user(request):
    user_id = request.GET.get('id')
    data = request.data

    if not user_id or 'email' not in data:
        return Response({"detail": "Missing user ID or email"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user, created = Users.objects.update_or_create(
            email=data['email'],
            defaults={
                'name': data.get('name', ''),
                'picture': data.get('image', ''),
                'date_joined': timezone.now(),
            }
        )

        token, _ = Token.objects.get_or_create(user=user)

        return Response({
            "message": "User created" if created else "User updated",
            "user_id": str(user.id),
            "email": user.email,
            "token": token.key,    # token untuk autentikasi
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    email = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(request, email=email, password=password)

    if user is not None:
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'username': user.email,
            'token': token.key,
            'scope': [aoi.id for aoi in user.areas_of_interest.all()]
        })
    return Response({'detail': 'Invalid credentials'}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_info_view(request):
    user = request.user
    return Response({
        'username': user.email,
        'token': request.auth.key if request.auth else None,
        'scope': [aoi.id for aoi in user.areas_of_interest.all()]
    })