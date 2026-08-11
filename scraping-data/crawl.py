import os
import json
import sqlite3
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import platform
import argparse

class BrowserHistoryCollector:
    def __init__(self, days=10, output_file='browser_history.json'):
        self.days = days
        self.output_file = output_file
        self.cutoff_date = datetime.now() - timedelta(days=days)
        self.history = {
            'chrome': [],
            'firefox': [],
            'collection_date': datetime.now().isoformat(),
            'metadata': {
                'days_collected': days,
                'cutoff_date': self.cutoff_date.isoformat(),
                'system': platform.system(),
                'python_version': platform.python_version()
            }
        }
        self.description = "Browser History Collector v1.0 - Extracts and stores browser history from Chrome and Firefox"

    def get_description(self):
        return self.description

    def get_chrome_history_path(self):
        system = platform.system()
        if system == 'Windows':
            return os.path.expanduser('~') + r'\AppData\Local\Google\Chrome\User Data\Default\History'
        elif system == 'Darwin':
            return os.path.expanduser('~') + '/Library/Application Support/Google/Chrome/Default/History'
        else:
            return os.path.expanduser('~') + '/.config/google-chrome/Default/History'

    def get_firefox_history_path(self):
        system = platform.system()
        if system == 'Windows':
            firefox_path = os.path.expanduser('~') + r'\AppData\Roaming\Mozilla\Firefox\Profiles'
        elif system == 'Darwin':
            firefox_path = os.path.expanduser('~') + '/Library/Application Support/Firefox/Profiles'
        else:
            firefox_path = os.path.expanduser('~') + '/.mozilla/firefox'
        
        if os.path.exists(firefox_path):
            for item in os.listdir(firefox_path):
                if item.endswith('.default') or item.endswith('.default-release'):
                    return os.path.join(firefox_path, item, 'places.sqlite')
        return None

    def collect_chrome_history(self):
        history_path = self.get_chrome_history_path()
        if not os.path.exists(history_path):
            return
        
        temp_path = 'chrome_history_temp.db'
        try:
            shutil.copy2(history_path, temp_path)
        except Exception:
            return
        
        try:
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            
            query = """
                SELECT url, title, visit_count, last_visit_time 
                FROM urls 
                WHERE last_visit_time > ?
                ORDER BY last_visit_time DESC
            """
            
            chrome_epoch = datetime(1601, 1, 1)
            cutoff_epoch = int((self.cutoff_date - chrome_epoch).total_seconds() * 1000000)
            
            cursor.execute(query, (cutoff_epoch,))
            results = cursor.fetchall()
            
            for row in results:
                visit_time = chrome_epoch + timedelta(microseconds=row[3])
                self.history['chrome'].append({
                    'url': row[0],
                    'title': row[1] if row[1] else 'No Title',
                    'visit_count': row[2],
                    'last_visit': visit_time.isoformat(),
                    'browser': 'Chrome'
                })
            
        except sqlite3.Error:
            pass
        finally:
            conn.close()
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def collect_firefox_history(self):
        history_path = self.get_firefox_history_path()
        if not history_path or not os.path.exists(history_path):
            return
        
        temp_path = 'firefox_history_temp.db'
        try:
            shutil.copy2(history_path, temp_path)
        except Exception:
            return
        
        try:
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            
            query = """
                SELECT url, title, visit_count, last_visit_date 
                FROM moz_places 
                WHERE last_visit_date > ?
                ORDER BY last_visit_date DESC
            """
            
            cutoff_epoch = int(self.cutoff_date.timestamp() * 1000000)
            
            cursor.execute(query, (cutoff_epoch,))
            results = cursor.fetchall()
            
            for row in results:
                visit_time = datetime.fromtimestamp(row[3] / 1000000)
                self.history['firefox'].append({
                    'url': row[0],
                    'title': row[1] if row[1] else 'No Title',
                    'visit_count': row[2],
                    'last_visit': visit_time.isoformat(),
                    'browser': 'Firefox'
                })
            
        except sqlite3.Error:
            pass
        finally:
            conn.close()
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def generate_statistics(self):
        total_chrome = len(self.history['chrome'])
        total_firefox = len(self.history['firefox'])
        total_visits = total_chrome + total_firefox
        
        return {
            'total_chrome': total_chrome,
            'total_firefox': total_firefox,
            'total_visits': total_visits,
            'date_range': f"{self.cutoff_date.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}",
            'has_chrome_data': total_chrome > 0,
            'has_firefox_data': total_firefox > 0
        }

    def save_to_json(self):
        try:
            statistics = self.generate_statistics()
            self.history['statistics'] = statistics
            
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception:
            return False

    def get_summary(self):
        stats = self.generate_statistics()
        return {
            'status': 'success',
            'collection_date': self.history['collection_date'],
            'statistics': stats,
            'output_file': self.output_file,
            'description': self.description
        }

    def run(self):
        self.collect_chrome_history()
        self.collect_firefox_history()
        success = self.save_to_json()
        
        if success:
            return self.get_summary()
        else:
            return {
                'status': 'failed',
                'description': self.description,
                'error': 'Failed to save JSON file'
            }

class BrowserHistoryCLI:
    def __init__(self):
        self.parser = self.create_parser()
        self.description = "Browser History Collector - Command line interface for extracting browser history"

    def create_parser(self):
        parser = argparse.ArgumentParser(
            description=self.description,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  python script.py                    Collect last 10 days of browser history
  python script.py -d 30              Collect last 30 days of browser history
  python script.py -o history.json    Save output to custom file
  python script.py -d 7 -o week.json  Collect last 7 days and save to week.json
            """
        )
        
        parser.add_argument(
            '-d', '--days',
            type=int,
            default=10,
            help='Number of days of history to collect (default: 10)'
        )
        
        parser.add_argument(
            '-o', '--output',
            type=str,
            default='browser_history.json',
            help='Output JSON file name (default: browser_history.json)'
        )
        
        parser.add_argument(
            '--version',
            action='version',
            version='Browser History Collector v1.0'
        )
        
        return parser

    def parse_arguments(self):
        return self.parser.parse_args()

    def run(self):
        args = self.parse_arguments()
        
        collector = BrowserHistoryCollector(
            days=args.days,
            output_file=args.output
        )
        
        result = collector.run()
        
        if result['status'] == 'success':
            stats = result['statistics']
            return {
                'status': 'success',
                'message': f"Browser history collected successfully",
                'output_file': result['output_file'],
                'total_visits': stats['total_visits'],
                'chrome_visits': stats['total_chrome'],
                'firefox_visits': stats['total_firefox'],
                'date_range': stats['date_range'],
                'description': collector.get_description()
            }
        else:
            return {
                'status': 'failed',
                'message': result.get('error', 'Unknown error occurred'),
                'description': result.get('description', '')
            }

def main():
    cli = BrowserHistoryCLI()
    result = cli.run()
    
    if result['status'] == 'success':
        print(f"STATUS: {result['status'].upper()}")
        print(f"DESCRIPTION: {result['description']}")
        print(f"OUTPUT: {result['output_file']}")
        print(f"DATE RANGE: {result['date_range']}")
        print(f"TOTAL VISITS: {result['total_visits']}")
        print(f"CHROME: {result['chrome_visits']} visits")
        print(f"FIREFOX: {result['firefox_visits']} visits")
    else:
        print(f"STATUS: {result['status'].upper()}")
        print(f"DESCRIPTION: {result['description']}")
        print(f"ERROR: {result['message']}")

if __name__ == "__main__":
    main()
