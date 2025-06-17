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
            'to_emails': [email.strip() for email in os.getenv('TO_EMAILS', '').split(',') if email.strip()]
        }
        
        # Tracking untuk mencegah duplicate notifications
        self.last_hotspot_id = self.get_last_hotspot_id()
        self.last_deforestation_id = self.get_last_deforestation_id()
        self.connection = None
        
        # TAMBAHAN: Queue untuk real-time notifications
        self.notification_queue = Queue()
        self.running = False
        
        # TAMBAHAN: Tracking untuk real-time monitoring
        self.last_hotspot_count = self.get_current_hotspot_count()
        self.last_deforestation_count = self.get_current_deforestation_count()
        
        logger.info(f"Service initialized - Last Hotspot ID: {self.last_hotspot_id}, Last Deforestation ID: {self.last_deforestation_id}")
        logger.info(f"Current counts - Hotspot: {self.last_hotspot_count}, Deforestation: {self.last_deforestation_count}")
        
        
    def connect_database(self):
        """Membuat koneksi ke PostgreSQL database"""
        try:
            self.connection = psycopg2.connect(**self.db_config)
            logger.info("Database connection established")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")
            return False

    def get_last_hotspot_id(self) -> int:
        """Mendapatkan ID terakhir dari HotspotAlert untuk tracking"""
        try:
            from data.models import HotspotAlert
            last_alert = HotspotAlert.objects.order_by('-id').first()
            return last_alert.id if last_alert else 0
        except Exception as e:
            logger.error(f"Error getting last hotspot ID: {str(e)}")
            return 0

    def get_last_deforestation_id(self) -> str:
        """Mendapatkan ID terakhir dari DeforestationAlerts untuk tracking"""
        try:
            from data.models import DeforestationAlerts
            last_alert = DeforestationAlerts.objects.order_by('-id').first()
            return last_alert.id if last_alert else ""
        except Exception as e:
            logger.error(f"Error getting last deforestation ID: {str(e)}")
            return ""
    
    # TAMBAHAN: Method untuk mendapatkan count saat ini
    def get_current_hotspot_count(self) -> int:
        """Mendapatkan jumlah total HotspotAlert saat ini"""
        try:
            from data.models import HotspotAlert
            return HotspotAlert.objects.count()
        except Exception as e:
            logger.error(f"Error getting hotspot count: {str(e)}")
            return 0
    
    def get_current_deforestation_count(self) -> int:
        """Mendapatkan jumlah total DeforestationAlerts saat ini"""
        try:
            from data.models import DeforestationAlerts
            return DeforestationAlerts.objects.count()
        except Exception as e:
            logger.error(f"Error getting deforestation count: {str(e)}")
            return 0
    
    # TAMBAHAN: Method untuk detect perubahan data
    def detect_data_changes(self) -> Dict[str, Any]:
        """Detect perubahan data dengan membandingkan count"""
        changes = {
            'hotspot_new': 0,
            'deforestation_new': 0,
            'has_changes': False
        }
        
        try:
            # Check hotspot changes
            current_hotspot_count = self.get_current_hotspot_count()
            if current_hotspot_count > self.last_hotspot_count:
                changes['hotspot_new'] = current_hotspot_count - self.last_hotspot_count
                changes['has_changes'] = True
                logger.info(f"Detected {changes['hotspot_new']} new hotspot alerts")
            
            # Check deforestation changes
            current_deforestation_count = self.get_current_deforestation_count()
            if current_deforestation_count > self.last_deforestation_count:
                changes['deforestation_new'] = current_deforestation_count - self.last_deforestation_count
                changes['has_changes'] = True
                logger.info(f"Detected {changes['deforestation_new']} new deforestation alerts")
            
            # Update counts jika ada perubahan
            if changes['has_changes']:
                self.last_hotspot_count = current_hotspot_count
                self.last_deforestation_count = current_deforestation_count
            
            return changes
            
        except Exception as e:
            logger.error(f"Error detecting data changes: {str(e)}")
            return changes
    
    # TAMBAHAN: Method untuk real-time monitoring
    def real_time_monitor(self, check_interval: int = 30):
        """Monitor real-time untuk perubahan data"""
        logger.info(f"Starting real-time monitor with {check_interval}s interval")
        
        while self.running:
            try:
                changes = self.detect_data_changes()
                
                if changes['has_changes']:
                    # Queue notification untuk processing
                    self.notification_queue.put({
                        'type': 'real_time',
                        'timestamp': datetime.now(),
                        'changes': changes
                    })
                    
                    logger.info(f"Queued real-time notification: {changes}")
                
                time.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Error in real-time monitor: {str(e)}")
                time.sleep(check_interval)
    
    # TAMBAHAN: Method untuk process notification queue
    def process_notification_queue(self):
        """Process notifications dari queue"""
        logger.info("Starting notification queue processor")
        
        while self.running:
            try:
                if not self.notification_queue.empty():
                    notification = self.notification_queue.get(timeout=1)
                    
                    if notification['type'] == 'real_time':
                        self.send_real_time_notification(notification)
                    
                    self.notification_queue.task_done()
                else:
                    time.sleep(1)
                    
            except Exception as e:
                if "Empty" not in str(e):  # Ignore empty queue timeout
                    logger.error(f"Error processing notification queue: {str(e)}")
                time.sleep(1)
    
    # TAMBAHAN: Method untuk kirim real-time notification
    def send_real_time_notification(self, notification):
        """Kirim email untuk real-time notification"""
        try:
            changes = notification['changes']
            timestamp = notification['timestamp']
            
            if not self.email_config['email_user'] or not self.email_config['to_emails']:
                logger.warning("Email configuration not complete, skipping real-time notification")
                return False
            
            # Ambil data terbaru untuk detail
            hotspot_alerts = []
            deforestation_alerts = []
            
            if changes['hotspot_new'] > 0:
                hotspot_alerts = self.get_latest_hotspot_alerts(changes['hotspot_new'])
            
            if changes['deforestation_new'] > 0:
                deforestation_alerts = self.get_latest_deforestation_alerts(changes['deforestation_new'])
            
            # Setup email
            msg = MIMEMultipart('alternative')
            total_new = changes['hotspot_new'] + changes['deforestation_new']
            
            msg['Subject'] = f"🚨 REAL-TIME ALERT - {total_new} New Alert(s) Detected"
            msg['From'] = self.email_config['from_email'] or self.email_config['email_user']
            msg['To'] = ', '.join(self.email_config['to_emails'])
            
            # Create HTML content
            html_content = self.format_real_time_email(hotspot_alerts, deforestation_alerts, timestamp)
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['email_user'], self.email_config['email_password'])
            
            for to_email in self.email_config['to_emails']:
                if to_email.strip():
                    server.send_message(msg, to_addrs=[to_email.strip()])
            
            server.quit()
            logger.info(f"Real-time email notification sent successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send real-time email notification: {str(e)}")
            return False
    
    # TAMBAHAN: Method untuk ambil data terbaru
    def get_latest_hotspot_alerts(self, count: int) -> List[Tuple]:
        """Ambil hotspot alerts terbaru"""
        try:
            if not self.connection:
                if not self.connect_database():
                    return []
            
            cursor = self.connection.cursor()
            
            query = """
                SELECT 
                    ha.id, ha.alert_date, ha.category, ha.confidence, ha.distance, ha.description,
                    aoi.name as area_name, COALESCE(aoi.description, aoi.name) as area_description,
                    h.lat as latitude, h.long as longitude, h.radius as brightness,
                    h.date as scan_date, h.sat as satellite, h.conf as hotspot_confidence,
                    'hotspot' as alert_type
                FROM data_hotspotalert ha
                JOIN data_areaofinterest aoi ON ha.area_of_interest_id = aoi.id
                JOIN data_hotspots h ON ha.hotspot_id = h.id
                ORDER BY ha.id DESC
                LIMIT %s
            """
            
            cursor.execute(query, (count,))
            alerts = cursor.fetchall()
            cursor.close()
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error getting latest hotspot alerts: {str(e)}")
            return []
    
    def get_latest_deforestation_alerts(self, count: int) -> List[Tuple]:
        """Ambil deforestation alerts terbaru"""
        try:
            if not self.connection:
                if not self.connect_database():
                    return []
            
            cursor = self.connection.cursor()
            
            query = """
                SELECT 
                    da.id, da.event_id, da.alert_date, da.created, da.confidence, da.area,
                    aoi.name as area_name, COALESCE(aoi.description, aoi.name) as area_description,
                    ST_AsText(ST_Centroid(da.geom)) as center_point, 'deforestation' as alert_type
                FROM data_deforestationalerts da
                JOIN data_areaofinterest aoi ON da.company_id = aoi.id
                ORDER BY da.id DESC
                LIMIT %s
            """
            
            cursor.execute(query, (count,))
            alerts = cursor.fetchall()
            cursor.close()
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error getting latest deforestation alerts: {str(e)}")
            return []
    
    # TAMBAHAN: Format email untuk real-time notification
    def format_real_time_email(self, hotspot_alerts: List[Tuple], deforestation_alerts: List[Tuple], timestamp: datetime) -> str:
        """Format email untuk real-time notification"""
        total_alerts = len(hotspot_alerts) + len(deforestation_alerts)
        
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; font-weight: bold; }}
                .header {{ color: #d9534f; }}
                .summary {{ background-color: #fff3cd; padding: 15px; border-radius: 5px; margin-bottom: 20px; border-left: 4px solid #ffc107; }}
                .real-time {{ color: #d9534f; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h2 class="header">🚨 REAL-TIME Environmental Alert</h2>
            
            <div class="summary">
                <h3 class="real-time">⚡ IMMEDIATE NOTIFICATION</h3>
                <p><strong>Detection Time:</strong> {timestamp.strftime('%Y-%m-%d %H:%M:%S WIB')}</p>
                <p><strong>Total New Alerts:</strong> {total_alerts}</p>
                <p><strong>New Hotspot Alerts:</strong> {len(hotspot_alerts)}</p>
                <p><strong>New Deforestation Alerts:</strong> {len(deforestation_alerts)}</p>
                <p class="real-time">⚠️ This is a real-time notification triggered by new data entry!</p>
            </div>
        """
        
        # Add hotspot alerts section
        if hotspot_alerts:
            html_content += self.format_hotspot_alerts_email(hotspot_alerts)
        
        # Add deforestation alerts section
        if deforestation_alerts:
            html_content += self.format_deforestation_alerts_email(deforestation_alerts)
        
        html_content += """
            <hr>
            <p><em>This is an automated REAL-TIME notification from Environmental Monitoring System.</em></p>
            <p><strong>Action Required:</strong> Please check the dashboard immediately and take appropriate action.</p>
            <p><strong>Dashboard:</strong> <a href="http://your-frontend-url.com">Monitoring Dashboard</a></p>
        </body>
        </html>
        """
        
        return html_content

    def check_new_hotspot_alerts(self) -> List[Tuple]:
        """Mengecek HotspotAlert baru berdasarkan ID yang lebih besar dari last_hotspot_id"""
        if not self.connection:
            if not self.connect_database():
                return []

        try:
            cursor = self.connection.cursor()

            # Query berdasarkan ID yang lebih besar dari last check
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
                    'hotspot' as alert_type
                FROM data_hotspotalert ha
                JOIN data_areaofinterest aoi ON ha.area_of_interest_id = aoi.id
                JOIN data_hotspots h ON ha.hotspot_id = h.id
                WHERE ha.id > %s
                ORDER BY ha.id ASC
            """

            cursor.execute(query, (self.last_hotspot_id,))
            new_alerts = cursor.fetchall()

            logger.debug(f"Checking hotspot alerts with ID > {self.last_hotspot_id}")
            logger.debug(f"Found {len(new_alerts)} new hotspot alerts")

            cursor.close()
            return new_alerts

        except Exception as e:
            logger.error(f"Error checking new hotspot alerts: {str(e)}")
            self.connection = None
            return []

    def check_new_deforestation_alerts(self) -> List[Tuple]:
        """Mengecek DeforestationAlerts baru berdasarkan ID yang lebih besar dari last_deforestation_id"""
        if not self.connection:
            if not self.connect_database():
                return []

        try:
            cursor = self.connection.cursor()

            # Query berdasarkan ID yang lebih besar dari last check
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
                    'deforestation' as alert_type
                FROM data_deforestationalerts da
                JOIN data_areaofinterest aoi ON da.company_id = aoi.id
                WHERE da.id > %s
                ORDER BY da.id ASC
            """

            cursor.execute(query, (self.last_deforestation_id,))
            new_alerts = cursor.fetchall()

            logger.debug(f"Checking deforestation alerts with ID > {self.last_deforestation_id}")
            logger.debug(f"Found {len(new_alerts)} new deforestation alerts")

            cursor.close()
            return new_alerts

        except Exception as e:
            logger.error(f"Error checking new deforestation alerts: {str(e)}")
            self.connection = None
            return []

    def update_last_ids(self, hotspot_alerts: List[Tuple], deforestation_alerts: List[Tuple]):
        """Update last IDs setelah notifikasi berhasil dikirim"""
        if hotspot_alerts:
            # ID ada di index 0
            latest_hotspot_id = max([alert[0] for alert in hotspot_alerts])
            self.last_hotspot_id = latest_hotspot_id
            logger.info(f"Updated last hotspot ID to: {self.last_hotspot_id}")

        if deforestation_alerts:
            # ID ada di index 0
            latest_deforestation_id = max([alert[0] for alert in deforestation_alerts])
            self.last_deforestation_id = latest_deforestation_id
            logger.info(f"Updated last deforestation ID to: {self.last_deforestation_id}")

    def format_hotspot_alerts_email(self, alerts: List[Tuple]) -> str:
        """Format HotspotAlert data untuk email notification"""
        if not alerts:
            return ""

        html_content = f"""
        <h3 style="color: #d9534f;">🔥 Hotspot Alerts ({len(alerts)} new)</h3>
        <table style="border-collapse: collapse; width: 100%; margin-bottom: 20px;">
            <tr style="background-color: #f2f2f2;">
                <th style="border: 1px solid #ddd; padding: 8px;">ID</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Area</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Category</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Location</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Distance (m)</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Confidence</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Satellite</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Date</th>
            </tr>
        """

        for alert in alerts:
            (id_val, alert_date, category, confidence, distance, description, 
             area_name, area_description, lat, lon, brightness, scan_date, satellite, hotspot_conf, alert_type) = alert

            location = f"{lat:.4f}, {lon:.4f}" if lat and lon else "N/A"

            # Color coding berdasarkan kategori
            if category == "BAHAYA":
                category_color = "#d9534f"  # Red
            elif category == "WASPADA":
                category_color = "#f0ad4e"  # Orange
            elif category == "PERHATIAN":
                category_color = "#337ab7"  # Blue
            else:
                category_color = "#5cb85c"  # Green (AMAN)

            distance_str = f"{distance:.0f}" if distance else "N/A"
            confidence_display = confidence if confidence else hotspot_conf

            html_content += f"""
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;">{id_val}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{area_name}</td>
                    <td style="border: 1px solid #ddd; padding: 8px; color: {category_color}; font-weight: bold;">{category}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{location}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{distance_str}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{confidence_display}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{satellite}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{alert_date}</td>
                </tr>
            """

        html_content += "</table>"
        return html_content

    def format_deforestation_alerts_email(self, alerts: List[Tuple]) -> str:
        """Format DeforestationAlerts data untuk email notification"""
        if not alerts:
            return ""

        html_content = f"""
        <h3 style="color: #5cb85c;">🌳 Deforestation Alerts ({len(alerts)} new)</h3>
        <table style="border-collapse: collapse; width: 100%; margin-bottom: 20px;">
            <tr style="background-color: #f2f2f2;">
                <th style="border: 1px solid #ddd; padding: 8px;">ID</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Event ID</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Area</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Area (ha)</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Confidence</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Alert Date</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Center Point</th>
            </tr>
        """

        for alert in alerts:
            (id_val, event_id, alert_date, created, confidence, area, 
             area_name, area_description, center_point, alert_type) = alert

            # Parse center point coordinates
            center_coords = "N/A"
            if center_point and "POINT(" in center_point:
                try:
                    coords = center_point.replace("POINT(", "").replace(")", "").split()
                    if len(coords) == 2:
                        center_coords = f"{float(coords[1]):.4f}, {float(coords[0]):.4f}"
                except:
                    center_coords = "N/A"

            area_str = f"{float(area):.2f}" if area else "N/A"

            html_content += f"""
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;">{id_val}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{event_id}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{area_name}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{area_str}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{confidence}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{alert_date}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{center_coords}</td>
                </tr>
            """

        html_content += "</table>"
        return html_content

    def format_combined_email(self, hotspot_alerts: List[Tuple], deforestation_alerts: List[Tuple]) -> str:
        """Format gabungan email notification untuk kedua jenis alert"""
        total_alerts = len(hotspot_alerts) + len(deforestation_alerts)

        if total_alerts == 0:
            return "No new alerts detected."

        # Hitung statistik
        high_priority_hotspots = len([a for a in hotspot_alerts if a[2] in ["BAHAYA", "WASPADA"]])
        high_confidence_deforestation = len([a for a in deforestation_alerts if a[4] and a[4] > 80])

        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; font-weight: bold; }}
                .header {{ color: #337ab7; }}
                .summary {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                .priority {{ color: #d9534f; font-weight: bold; }}
                .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; }}
            </style>
        </head>
        <body>
            <h2 class="header">🚨 Environmental Monitoring Alert System</h2>
            
            <div class="summary">
                <h3>Alert Summary</h3>
                <p><strong>Total New Alerts:</strong> {total_alerts}</p>
                <p><strong>Hotspot Alerts:</strong> {len(hotspot_alerts)} ({high_priority_hotspots} high priority)</p>
                <p><strong>Deforestation Alerts:</strong> {len(deforestation_alerts)} ({high_confidence_deforestation} high confidence)</p>
                <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S WIB')}</p>
                {f'<p class="priority">⚠️ {high_priority_hotspots + high_confidence_deforestation} alerts require immediate attention!</p>' if (high_priority_hotspots + high_confidence_deforestation) > 0 else ''}
            </div>
        """

        # Add hotspot alerts section
        if hotspot_alerts:
            html_content += self.format_hotspot_alerts_email(hotspot_alerts)

        # Add deforestation alerts section
        if deforestation_alerts:
            html_content += self.format_deforestation_alerts_email(deforestation_alerts)

        html_content += """
            <div class="footer">
                <hr>
                <p><em>This is an automated notification from Environmental Monitoring System.</em></p>
                <p>Please check the dashboard for more details and take appropriate action if necessary.</p>
                <p><strong>Dashboard:</strong> <a href="https://monitoringapp-1075290745302.asia-southeast1.run.app/signin">Monitoring Dashboard</a></p>
                <p><small>To stop receiving these notifications, please contact your system administrator.</small></p>
            </div>
        </body>
        </html>
        """

        return html_content

    def send_email_notification(self, hotspot_alerts: List[Tuple], deforestation_alerts: List[Tuple]):
        """Mengirim email notification untuk alert baru"""
        total_alerts = len(hotspot_alerts) + len(deforestation_alerts)

        if total_alerts == 0:
            return False

        try:
            if not self.email_config['email_user'] or not self.email_config['to_emails']:
                logger.warning("Email configuration not complete, skipping notification")
                return False

            # Setup email
            msg = MIMEMultipart('alternative')

            # Priority berdasarkan jenis alert
            priority_count = len([a for a in hotspot_alerts if a[2] in ["BAHAYA", "WASPADA"]]) + \
                           len([a for a in deforestation_alerts if a[4] and a[4] > 80])

            priority_text = " [HIGH PRIORITY]" if priority_count > 0 else ""

            msg['Subject'] = f"🚨 Environmental Alert{priority_text} - {total_alerts} New Alert(s)"
            msg['From'] = self.email_config['from_email'] or self.email_config['email_user']
            msg['To'] = ', '.join(self.email_config['to_emails'])

            # Create HTML content
            html_content = self.format_combined_email(hotspot_alerts, deforestation_alerts)
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)

            # Send email
            server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['email_user'], self.email_config['email_password'])

            for to_email in self.email_config['to_emails']:
                if to_email.strip():
                    server.send_message(msg, to_addrs=[to_email.strip()])

            server.quit()
            logger.info(f"Email notification sent successfully to {len(self.email_config['to_emails'])} recipients")
            logger.info(f"Alert breakdown - Hotspot: {len(hotspot_alerts)}, Deforestation: {len(deforestation_alerts)}")

            return True

        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")
            return False

    def run_monitoring(self, check_interval: int = 300):
        """Main monitoring loop dengan logika yang diperbaiki + real-time monitoring"""
        logger.info("Starting Enhanced Environmental Monitoring Notification Service...")
        logger.info(f"Batch check interval: {check_interval} seconds")
        logger.info(f"Real-time monitoring: ENABLED (30s interval)")
        logger.info(f"Email recipients: {len(self.email_config['to_emails'])}")
        
        self.running = True
        
        # TAMBAHAN: Start real-time monitoring thread
        real_time_thread = threading.Thread(target=self.real_time_monitor, args=(30,))
        real_time_thread.daemon = True
        real_time_thread.start()
        logger.info("Real-time monitoring thread started")
        
        # TAMBAHAN: Start notification queue processor thread
        queue_processor_thread = threading.Thread(target=self.process_notification_queue)
        queue_processor_thread.daemon = True
        queue_processor_thread.start()
        logger.info("Notification queue processor thread started")

        consecutive_errors = 0
        max_consecutive_errors = 5

        while True:
            try:
                # Batch monitoring (fallback untuk memastikan tidak ada yang terlewat)
                hotspot_alerts = self.check_new_hotspot_alerts()
                deforestation_alerts = self.check_new_deforestation_alerts()

                total_alerts = len(hotspot_alerts) + len(deforestation_alerts)

                if total_alerts > 0:
                    # Send batch notification
                    success = self.send_email_notification(hotspot_alerts, deforestation_alerts)

                    if success:
                        logger.info(f"Sent batch notification for {total_alerts} alerts (Hotspot: {len(hotspot_alerts)}, Deforestation: {len(deforestation_alerts)})")
                        
                        # Update tracking IDs hanya jika email berhasil dikirim
                        self.update_last_ids(hotspot_alerts, deforestation_alerts)
                        consecutive_errors = 0
                    else:
                        logger.error("Failed to send batch notification, will retry on next cycle")
                        consecutive_errors += 1
                else:
                    logger.debug("No new alerts detected in batch check")
                    consecutive_errors = 0

                # Check if too many consecutive errors
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Too many consecutive errors ({consecutive_errors}), stopping service")
                    break

                # Wait before next check
                time.sleep(check_interval)

            except KeyboardInterrupt:
                logger.info("Monitoring service stopped by user")
                self.running = False
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Unexpected error in monitoring loop: {str(e)}")

                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Too many consecutive errors ({consecutive_errors}), stopping service")
                    break

                time.sleep(check_interval)

        # Cleanup
        self.running = False
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")

def main():
    """Main function untuk menjalankan service"""
    # Buat direktori logs jika belum ada
    os.makedirs('/app/logs', exist_ok=True)

    # Initialize service
    service = HotspotNotificationService()

    # Get check interval from environment variable (default 300 seconds = 5 menit)
    check_interval = int(os.getenv('CHECK_INTERVAL', '300'))

    # Start monitoring
    service.run_monitoring(check_interval)

if __name__ == "__main__":
    main()
