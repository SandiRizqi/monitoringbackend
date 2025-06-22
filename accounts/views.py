#accounts/views.py
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate
from .models import Users, AccountNotificationSetting
from .serializers import AccountNotificationSettingSerializer
from rest_framework import status
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView
from rest_framework.authentication import TokenAuthentication
from notifications.services import NotificationService



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




class AccountNotificationSettingView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            setting, _ = AccountNotificationSetting.objects.get_or_create(user=request.user)
            serializer = AccountNotificationSettingSerializer(setting)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        try:
            setting, _ = AccountNotificationSetting.objects.get_or_create(user=request.user)
            serializer = AccountNotificationSettingSerializer(setting, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save(user=request.user)
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_test_notification(request):
    """Endpoint untuk mengirim test notification"""
    try:
        user = request.user
        notification_type = request.data.get('type', 'hotspot')
        
        if notification_type not in ['hotspot', 'deforestation']:
            return Response(
                {'error': 'Invalid notification type. Use "hotspot" or "deforestation"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        success = NotificationService.send_test_notification(user, notification_type)
        
        if success:
            return Response({'message': f'Test {notification_type} notification sent successfully'})
        else:
            return Response(
                {'error': 'Failed to send test notification'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([AllowAny])  # Untuk webhook dari sistem eksternal
def webhook_notification_receiver(request):
    """Endpoint untuk menerima notifikasi dari sistem eksternal"""
    try:
        # Validasi API key atau token jika diperlukan
        api_key = request.headers.get('X-API-Key')
        if api_key != 'your-secret-api-key':  # Ganti dengan API key yang aman
            return Response(
                {'error': 'Invalid API key'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        data = request.data
        notification_type = data.get('type')
        
        # Log incoming webhook
        logger.info(f"Received webhook notification: {notification_type}")
        
        # Process webhook data sesuai kebutuhan
        # Misalnya: update database, trigger notifikasi, dll.
        
        return Response({'message': 'Webhook received successfully'})
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )