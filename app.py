import os
import sys
import django
import psycopg2
import smtplib
import time
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import json
import threading
from queue import Queue

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'monitoringbackend.settings')
django.setup()

from django.conf import settings
from data.models import HotspotAlert, DeforestationAlerts, AreaOfInterest, Hotspots
from accounts.models import Users

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/notification.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HotspotNotificationService:
    def __init__(self):
        """Initialize notification service dengan konfigurasi email dan database"""
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'monitoring_db'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'password')
        }
        
        self.email_config = {
            'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': int(os.getenv('SMTP_PORT', '587')),
            'email_user': os.getenv('EMAIL_USER', ''),
            'email_password': os.getenv('EMAIL_PASSWORD', ''),
            'from_email': os.getenv('FROM_EMAIL', ''),
        }
        
        # Tracking untuk mencegah duplicate notifications per user
        self.user_last_hotspot_id = {}
        self.user_last_deforestation_id = {}
        self.connection = None
        
        # Queue untuk real-time notifications
        self.notification_queue = Queue()
        self.running = False
        
        # Initialize tracking untuk setiap user
        self.initialize_user_tracking()
        
        logger.info("Service initialized with per-user tracking")

    def initialize_user_tracking(self):
        """Initialize tracking untuk setiap user berdasarkan AOI mereka"""
        try:
            users = Users.objects.all()
            for user in users:
                # Get last hotspot alert ID untuk user ini
                last_hotspot = HotspotAlert.objects.filter(
                    area_of_interest__users_aoi=user
                ).order_by('-id').first()
                self.user_last_hotspot_id[user.id] = last_hotspot.id if last_hotspot else 0
                
                # Get last deforestation alert ID untuk user ini
                last_deforestation = DeforestationAlerts.objects.filter(
                    company__users_aoi=user
                ).order_by('-id').first()
                self.user_last_deforestation_id[user.id] = last_deforestation.id if last_deforestation else ""
                
                logger.info(f"User {user.email} - Last Hotspot ID: {self.user_last_hotspot_id[user.id]}, Last Deforestation ID: {self.user_last_deforestation_id[user.id]}")
                
        except Exception as e:
            logger.error(f"Error initializing user tracking: {str(e)}")

    def connect_database(self):
        """Membuat koneksi ke PostgreSQL database"""
        try:
            self.connection = psycopg2.connect(**self.db_config)
            logger.info("Database connection established")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")
            return False

    def get_users_with_aoi(self) -> List[Users]:
        """Mendapatkan semua user yang memiliki AOI"""
        try:
            return Users.objects.filter(areas_of_interest__isnull=False).distinct()
        except Exception as e:
            logger.error(f"Error getting users with AOI: {str(e)}")
            return []

    def check_new_hotspot_alerts_for_user(self, user: Users) -> List[Tuple]:
        """Mengecek HotspotAlert baru untuk user tertentu berdasarkan AOI mereka"""
        if not self.connection:
            if not self.connect_database():
                return []

        try:
            cursor = self.connection.cursor()
            last_id = self.user_last_hotspot_id.get(user.id, 0)
            
            # Query berdasarkan AOI milik user dan ID yang lebih besar dari last check
            query = """
            SELECT 
                ha.id,
                ha.alert_date,
                ha.category,
                ha.confidence,
                ha.distance,
                ha.description,
                aoi.name as area_name,
                COALESCE(aoi.description, aoi.name) as area_description,
                h.lat as latitude,
                h.long as longitude,
                h.radius as brightness,
                h.date as scan_date,
                h.sat as satellite,
                h.conf as hotspot_confidence,
                'hotspot' as alert_type,
                %s as user_id,
                %s as user_email
            FROM data_hotspotalert ha
            JOIN data_areaofinterest aoi ON ha.area_of_interest_id = aoi.id
            JOIN accounts_users_areas_of_interest uaoi ON aoi.id = uaoi.areaofinterest_id
            JOIN data_hotspots h ON ha.hotspot_id = h.id
            WHERE uaoi.users_id = %s 
            AND ha.id > %s
            ORDER BY ha.id ASC
            """
            
            cursor.execute(query, (user.id, user.email, user.id, last_id))
            new_alerts = cursor.fetchall()
            
            logger.debug(f"User {user.email} - Checking hotspot alerts with ID > {last_id}")
            logger.debug(f"User {user.email} - Found {len(new_alerts)} new hotspot alerts")
            
            cursor.close()
            return new_alerts
            
        except Exception as e:
            logger.error(f"Error checking new hotspot alerts for user {user.email}: {str(e)}")
            self.connection = None
            return []

    def check_new_deforestation_alerts_for_user(self, user: Users) -> List[Tuple]:
        """Mengecek DeforestationAlerts baru untuk user tertentu berdasarkan AOI mereka"""
        if not self.connection:
            if not self.connect_database():
                return []

        try:
            cursor = self.connection.cursor()
            last_id = self.user_last_deforestation_id.get(user.id, "")
            
            # Query berdasarkan AOI milik user dan ID yang lebih besar dari last check
            query = """
            SELECT 
                da.id,
                da.event_id,
                da.alert_date,
                da.created,
                da.confidence,
                da.area,
                aoi.name as area_name,
                COALESCE(aoi.description, aoi.name) as area_description,
                ST_AsText(ST_Centroid(da.geom)) as center_point,
                'deforestation' as alert_type,
                %s as user_id,
                %s as user_email
            FROM data_deforestationalerts da
            JOIN data_areaofinterest aoi ON da.company_id = aoi.id
            JOIN accounts_users_areas_of_interest uaoi ON aoi.id = uaoi.areaofinterest_id
            WHERE uaoi.users_id = %s 
            AND da.id > %s
            ORDER BY da.id ASC
            """
            
            cursor.execute(query, (user.id, user.email, user.id, last_id))
            new_alerts = cursor.fetchall()
            
            logger.debug(f"User {user.email} - Checking deforestation alerts with ID > {last_id}")
            logger.debug(f"User {user.email} - Found {len(new_alerts)} new deforestation alerts")
            
            cursor.close()
            return new_alerts
            
        except Exception as e:
            logger.error(f"Error checking new deforestation alerts for user {user.email}: {str(e)}")
            self.connection = None
            return []

    def update_user_last_ids(self, user: Users, hotspot_alerts: List[Tuple], deforestation_alerts: List[Tuple]):
        """Update last IDs untuk user tertentu setelah notifikasi berhasil dikirim"""
        if hotspot_alerts:
            latest_hotspot_id = max([alert[0] for alert in hotspot_alerts])
            self.user_last_hotspot_id[user.id] = latest_hotspot_id
            logger.info(f"User {user.email} - Updated last hotspot ID to: {latest_hotspot_id}")
        
        if deforestation_alerts:
            latest_deforestation_id = max([alert[0] for alert in deforestation_alerts])
            self.user_last_deforestation_id[user.id] = latest_deforestation_id
            logger.info(f"User {user.email} - Updated last deforestation ID to: {latest_deforestation_id}")

    def send_hotspot_email_notification(self, user: Users, alerts: List[Tuple]) -> bool:
        """Kirim email notifikasi khusus untuk hotspot alerts"""
        try:
            if not self.email_config['email_user'] or not user.email:
                logger.warning(f"Email configuration incomplete for user {user.email}")
                return False

            # Setup email dengan subject khusus hotspot
            msg = MIMEMultipart('alternative')
            high_priority_count = len([alert for alert in alerts if alert[2] in ['BAHAYA', 'WASPADA']])
            
            msg['Subject'] = f"🔥 HOTSPOT ALERT - {len(alerts)} Titik Panas Terdeteksi di Area Anda"
            if high_priority_count > 0:
                msg['Subject'] = f"🚨 URGENT HOTSPOT ALERT - {high_priority_count} Titik Panas Prioritas Tinggi!"
                
            msg['From'] = self.email_config['from_email'] or self.email_config['email_user']
            msg['To'] = user.email

            # Create HTML content khusus hotspot
            html_content = self.format_hotspot_email(user, alerts)
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)

            # Send email
            server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['email_user'], self.email_config['email_password'])
            server.send_message(msg, to_addrs=[user.email])
            server.quit()

            logger.info(f"Hotspot email notification sent to {user.email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send hotspot email to {user.email}: {str(e)}")
            return False

    def send_deforestation_email_notification(self, user: Users, alerts: List[Tuple]) -> bool:
        """Kirim email notifikasi khusus untuk deforestation alerts"""
        try:
            if not self.email_config['email_user'] or not user.email:
                logger.warning(f"Email configuration incomplete for user {user.email}")
                return False

            # Setup email dengan subject khusus deforestation
            msg = MIMEMultipart('alternative')
            total_area = sum([float(alert[5]) for alert in alerts if alert[5]])
            high_confidence_count = len([alert for alert in alerts if alert[4] and alert[4] >= 5])
            
            msg['Subject'] = f"🌳 DEFORESTATION ALERT - {len(alerts)} Deforestasi Terdeteksi ({total_area:.2f} ha)"
            if high_confidence_count > 0:
                msg['Subject'] = f"⚠️ CRITICAL DEFORESTATION - {high_confidence_count} Deforestasi Confidence Tinggi!"
                
            msg['From'] = self.email_config['from_email'] or self.email_config['email_user']
            msg['To'] = user.email

            # Create HTML content khusus deforestation
            html_content = self.format_deforestation_email(user, alerts)
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)

            # Send email
            server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['email_user'], self.email_config['email_password'])
            server.send_message(msg, to_addrs=[user.email])
            server.quit()

            logger.info(f"Deforestation email notification sent to {user.email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send deforestation email to {user.email}: {str(e)}")
            return False

    def format_hotspot_email(self, user: Users, alerts: List[Tuple]) -> str:
        """Format email khusus untuk hotspot alerts"""
        high_priority_count = len([alert for alert in alerts if alert[2] in ['BAHAYA', 'WASPADA']])
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #ff4444; color: white; padding: 15px; border-radius: 5px; }}
                .content {{ margin: 20px 0; }}
                .alert-table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                .alert-table th, .alert-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                .alert-table th {{ background-color: #f2f2f2; }}
                .priority-high {{ background-color: #ffebee; }}
                .priority-medium {{ background-color: #fff3e0; }}
                .priority-low {{ background-color: #e8f5e8; }}
                .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>🔥 HOTSPOT ALERT - Area Monitoring System</h2>
                <p>Halo {user.name or user.email},</p>
                <p><strong>{len(alerts)} titik panas baru</strong> terdeteksi di area yang Anda monitor!</p>
                {f'<p style="color: #ffff00;"><strong>⚠️ {high_priority_count} alert memerlukan perhatian segera!</strong></p>' if high_priority_count > 0 else ''}
            </div>
            
            <div class="content">
                <h3>Detail Hotspot Alerts:</h3>
                <table class="alert-table">
                    <thead>
                        <tr>
                            <th>Area</th>
                            <th>Kategori</th>
                            <th>Lokasi</th>
                            <th>Jarak (m)</th>
                            <th>Confidence</th>
                            <th>Satelit</th>
                            <th>Tanggal</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for alert in alerts:
            id_val, alert_date, category, confidence, distance, description, area_name, area_description, lat, lng, brightness, scan_date, satellite, hotspot_confidence, alert_type, user_id, user_email = alert
            
            location = f"{lat:.4f}, {lng:.4f}" if lat and lng else "N/A"
            distance_str = f"{distance:.2f}" if distance else "N/A"
            confidence_display = f"{confidence}" if confidence else f"{hotspot_confidence}" if hotspot_confidence else "N/A"
            
            # Tentukan class CSS berdasarkan kategori
            row_class = ""
            if category in ['BAHAYA']:
                row_class = "priority-high"
            elif category in ['WASPADA']:
                row_class = "priority-medium"
            else:
                row_class = "priority-low"
            
            html_content += f"""
                        <tr class="{row_class}">
                            <td>{area_name}</td>
                            <td><strong>{category}</strong></td>
                            <td>{location}</td>
                            <td>{distance_str}</td>
                            <td>{confidence_display}</td>
                            <td>{satellite or 'N/A'}</td>
                            <td>{alert_date}</td>
                        </tr>
            """
        
        html_content += f"""
                    </tbody>
                </table>
                
                <div style="margin: 20px 0; padding: 15px; background-color: #f9f9f9; border-radius: 5px;">
                    <h4>📊 Ringkasan Alert:</h4>
                    <ul>
                        <li><strong>Total Alert:</strong> {len(alerts)}</li>
                        <li><strong>Prioritas Tinggi (Bahaya/Waspada):</strong> {high_priority_count}</li>
                        <li><strong>Waktu Deteksi:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S WIB')}</li>
                    </ul>
                </div>
                
                <div style="margin: 20px 0; padding: 15px; background-color: #e3f2fd; border-radius: 5px;">
                    <h4>🎯 Tindakan yang Disarankan:</h4>
                    <ul>
                        <li>Segera cek dashboard monitoring untuk detail lokasi</li>
                        <li>Koordinasi dengan tim lapangan untuk verifikasi</li>
                        <li>Siapkan tindakan pencegahan jika diperlukan</li>
                        {f'<li style="color: #d32f2f;"><strong>URGENT: {high_priority_count} lokasi memerlukan tindakan segera!</strong></li>' if high_priority_count > 0 else ''}
                    </ul>
                </div>
            </div>
            
            <div class="footer">
                <p><em>Email ini dikirim secara otomatis oleh Environmental Monitoring System.</em></p>
                <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S WIB')}</p>
            </div>
        </body>
        </html>
        """
        
        return html_content

    def format_deforestation_email(self, user: Users, alerts: List[Tuple]) -> str:
        """Format email khusus untuk deforestation alerts"""
        total_area = sum([float(alert[5]) for alert in alerts if alert[5]])
        high_confidence_count = len([alert for alert in alerts if alert[4] and alert[4] >= 5])
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #2e7d32; color: white; padding: 15px; border-radius: 5px; }}
                .content {{ margin: 20px 0; }}
                .alert-table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                .alert-table th, .alert-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                .alert-table th {{ background-color: #f2f2f2; }}
                .confidence-high {{ background-color: #ffebee; }}
                .confidence-medium {{ background-color: #fff3e0; }}
                .confidence-low {{ background-color: #e8f5e8; }}
                .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>🌳 DEFORESTATION ALERT - Area Monitoring System</h2>
                <p>Halo {user.name or user.email},</p>
                <p><strong>{len(alerts)} deforestasi baru</strong> terdeteksi di area yang Anda monitor!</p>
                <p><strong>Total Area Terdeforestasi: {total_area:.2f} hektar</strong></p>
                {f'<p style="color: #ffff00;"><strong>⚠️ {high_confidence_count} alert dengan confidence tinggi!</strong></p>' if high_confidence_count > 0 else ''}
            </div>
            
            <div class="content">
                <h3>Detail Deforestation Alerts:</h3>
                <table class="alert-table">
                    <thead>
                        <tr>
                            <th>Event ID</th>
                            <th>Area</th>
                            <th>Luas (ha)</th>
                            <th>Confidence</th>
                            <th>Tanggal Alert</th>
                            <th>Koordinat Pusat</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for alert in alerts:
            id_val, event_id, alert_date, created, confidence, area, area_name, area_description, center_point, alert_type, user_id, user_email = alert
            
            area_str = f"{float(area):.2f}" if area else "N/A"
            confidence_val = confidence if confidence else 0
            
            # Extract coordinates dari center_point (format: POINT(lng lat))
            center_coords = "N/A"
            if center_point and "POINT" in center_point:
                try:
                    coords = center_point.replace("POINT(", "").replace(")", "").split()
                    if len(coords) == 2:
                        center_coords = f"{float(coords[1]):.4f}, {float(coords[0]):.4f}"
                except:
                    center_coords = "N/A"
            
            # Tentukan class CSS berdasarkan confidence
            row_class = ""
            if confidence_val >= 5:
                row_class = "confidence-high"
            elif confidence_val >= 3:
                row_class = "confidence-medium"
            else:
                row_class = "confidence-low"
            
            html_content += f"""
                        <tr class="{row_class}">
                            <td>{event_id}</td>
                            <td>{area_name}</td>
                            <td>{area_str}</td>
                            <td>{confidence_val}</td>
                            <td>{alert_date}</td>
                            <td>{center_coords}</td>
                        </tr>
            """
        
        html_content += f"""
                    </tbody>
                </table>
                
                <div style="margin: 20px 0; padding: 15px; background-color: #f9f9f9; border-radius: 5px;">
                    <h4>📊 Ringkasan Deforestation:</h4>
                    <ul>
                        <li><strong>Total Event:</strong> {len(alerts)}</li>
                        <li><strong>Total Area Terdeforestasi:</strong> {total_area:.2f} hektar</li>
                        <li><strong>Confidence Tinggi (≥5):</strong> {high_confidence_count}</li>
                        <li><strong>Rata-rata Confidence:</strong> {sum([alert[4] for alert in alerts if alert[4]])/len([alert[4] for alert in alerts if alert[4]]):.1f if [alert[4] for alert in alerts if alert[4]] else 0}</li>
                        <li><strong>Waktu Deteksi:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S WIB')}</li>
                    </ul>
                </div>
                
                <div style="margin: 20px 0; padding: 15px; background-color: #e8f5e8; border-radius: 5px;">
                    <h4>🌿 Tindakan yang Disarankan:</h4>
                    <ul>
                        <li>Segera cek dashboard untuk analisis detail area terdeforestasi</li>
                        <li>Koordinasi dengan tim konservasi untuk investigasi lapangan</li>
                        <li>Dokumentasi dan laporkan ke otoritas terkait</li>
                        <li>Evaluasi penyebab dan rencana mitigasi</li>
                        {f'<li style="color: #d32f2f;"><strong>PRIORITY: {high_confidence_count} area dengan confidence tinggi perlu investigasi segera!</strong></li>' if high_confidence_count > 0 else ''}
                    </ul>
                </div>
            </div>
            
            <div class="footer">
                <p><em>Email ini dikirim secara otomatis oleh Environmental Monitoring System.</em></p>
                <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S WIB')}</p>
            </div>
        </body>
        </html>
        """
        
        return html_content

    def run_periodic_check(self, check_interval: int = 300):
        """Jalankan pengecekan berkala untuk semua user"""
        logger.info(f"Starting periodic check with {check_interval}s interval")
        
        while True:
            try:
                users = self.get_users_with_aoi()
                logger.info(f"Checking alerts for {len(users)} users")
                
                for user in users:
                    try:
                        # Check hotspot alerts untuk user ini
                        hotspot_alerts = self.check_new_hotspot_alerts_for_user(user)
                        
                        # Check deforestation alerts untuk user ini
                        deforestation_alerts = self.check_new_deforestation_alerts_for_user(user)
                        
                        # Kirim email terpisah untuk hotspot jika ada
                        if hotspot_alerts:
                            logger.info(f"Found {len(hotspot_alerts)} new hotspot alerts for user {user.email}")
                            if self.send_hotspot_email_notification(user, hotspot_alerts):
                                self.update_user_last_ids(user, hotspot_alerts, [])
                        
                        # Kirim email terpisah untuk deforestation jika ada
                        if deforestation_alerts:
                            logger.info(f"Found {len(deforestation_alerts)} new deforestation alerts for user {user.email}")
                            if self.send_deforestation_email_notification(user, deforestation_alerts):
                                self.update_user_last_ids(user, [], deforestation_alerts)
                        
                        if not hotspot_alerts and not deforestation_alerts:
                            logger.debug(f"No new alerts for user {user.email}")
                            
                    except Exception as e:
                        logger.error(f"Error processing alerts for user {user.email}: {str(e)}")
                        continue
                
                logger.info(f"Completed check cycle, sleeping for {check_interval} seconds")
                time.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Error in periodic check: {str(e)}")
                time.sleep(check_interval)

    def start_real_time_monitoring(self, check_interval: int = 30):
        """Start real-time monitoring dengan threading"""
        self.running = True
        
        # Start periodic check thread
        periodic_thread = threading.Thread(target=self.run_periodic_check, args=(check_interval,))
        periodic_thread.daemon = True
        periodic_thread.start()
        
        logger.info("Real-time monitoring started")
        
        try:
            # Keep main thread alive
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping real-time monitoring...")
            self.running = False

    def stop_monitoring(self):
        """Stop monitoring service"""
        self.running = False
        if self.connection:
            self.connection.close()
        logger.info("Monitoring service stopped")

def main():
    """Main function untuk menjalankan service"""
    logger.info("Starting Hotspot Notification Service...")
    
    service = HotspotNotificationService()
    
    try:
        # Start real-time monitoring (default 5 menit interval)
        service.start_real_time_monitoring(check_interval=300)
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Service error: {str(e)}")
    finally:
        service.stop_monitoring()
        logger.info("Service stopped")

if __name__ == "__main__":
    main()
