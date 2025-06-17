import unittest
from unittest.mock import patch, MagicMock
import psutil
import requests
from monitoring_agent import app, collect_metrics, count_requests

class TestMonitoringAgent(unittest.TestCase):
    # Ініціалізація перед кожним тестом
    def setUp(self):
        self.app = app.test_client()  # Створюємо тестового клієнта для Flask
        self.app.testing = True  # Увімкнення тестового режиму

    # Тест збору метрик
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    @patch('psutil.pids')
    @patch('requests.get')
    def test_collect_metrics(self, mock_requests, mock_pids, mock_disk, mock_memory, mock_cpu):
        # Мокування використання CPU
        mock_cpu.return_value = 50.0

        # Мокування використання пам’яті
        mock_memory.return_value = MagicMock(
            total=1000000000,
            used=500000000,
            available=500000000
        )

        # Мокування використання диска
        mock_disk.return_value = MagicMock(
            total=2000000000,
            used=1000000000,
            free=1000000000
        )

        # Мокування кількості процесів
        mock_pids.return_value = [1, 2, 3, 4, 5]

        # Мокування мережевого запиту
        mock_requests.return_value = MagicMock()
        mock_requests.return_value.elapsed.total_seconds.return_value = 0.1

        # Отримуємо метрики
        metrics = collect_metrics()
        metrics_dict = {line.split('{')[0]: line for line in metrics.split('\n')}  # Створюємо словник метрик

        # Тест метрики CPU
        cpu_metric = metrics_dict['system_cpu_usage_percent']
        self.assertIn('50.0', cpu_metric)  # Перевіряємо, чи містить метрика правильне значення

        # Тест метрик пам’яті
        mem_total = metrics_dict['system_memory_total_bytes']
        mem_used = metrics_dict['system_memory_used_bytes']
        mem_free = metrics_dict['system_memory_free_bytes']
        self.assertIn('1000000000', mem_total)  # Перевіряємо загальний обсяг пам’яті
        self.assertIn('500000000', mem_used)  # Перевіряємо використану пам’ять
        self.assertIn('500000000', mem_free)  # Перевіряємо вільну пам’ять

        # Тест метрик диска
        disk_total = metrics_dict['system_disk_total_bytes']
        disk_used = metrics_dict['system_disk_used_bytes']
        disk_free = metrics_dict['system_disk_free_bytes']
        self.assertIn('2000000000', disk_total)  # Перевіряємо загальний обсяг диска
        self.assertIn('1000000000', disk_used)  # Перевіряємо використаний обсяг диска
        self.assertIn('1000000000', disk_free)  # Перевіряємо вільний обсяг диска

        # Тест кількості процесів
        process_metric = metrics_dict['system_active_processes_count']
        self.assertIn('5', process_metric)  # Перевіряємо кількість активних процесів

        # Тест затримки мережі - перевіряємо будь-яке невід’ємне значення
        network_metric = metrics_dict['system_network_latency_ms']
        self.assertRegex(network_metric, r'system_network_latency_ms{host="[^"]+"} \d+(?:\.\d+)?$')  # Перевіряємо формат і числове значення

    # Тест формату метрик
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    @patch('psutil.pids')
    @patch('requests.get')
    def test_metrics_format(self, mock_requests, mock_pids, mock_disk, mock_memory, mock_cpu):
        # Мокування всіх необхідних значень
        mock_cpu.return_value = 50.0
        mock_memory.return_value = MagicMock(
            total=1000000000,
            used=500000000,
            available=500000000
        )
        mock_disk.return_value = MagicMock(
            total=2000000000,
            used=1000000000,
            free=1000000000
        )
        mock_pids.return_value = [1, 2, 3, 4, 5]
        mock_requests.return_value = MagicMock()
        mock_requests.return_value.elapsed.total_seconds.return_value = 0.1

        # Отримуємо метрики
        metrics = collect_metrics()
        metrics_list = metrics.split('\n')  # Розбиваємо рядок на список метрик

        # Тест на наявність усіх очікуваних метрик
        expected_metrics = [
            'system_cpu_usage_percent',
            'system_memory_total_bytes',
            'system_memory_used_bytes',
            'system_memory_free_bytes',
            'system_disk_total_bytes',
            'system_disk_used_bytes',
            'system_disk_free_bytes',
            'system_network_latency_ms',
            'system_active_processes_count',
            'system_server_response_time_ms',
            'system_server_request_count'
        ]

        for metric in expected_metrics:
            self.assertTrue(
                any(metric in line for line in metrics_list),
                f"Метрика {metric} не знайдена у виводі"
            )

        # Тест коректності формату кожної метрики
        for line in metrics_list:
            # Розбиваємо рядок на частини
            parts = line.split(' ')
            self.assertEqual(len(parts), 2, f"Рядок метрики '{line}' має містити рівно дві частини")
            
            # Перевіряємо назву метрики та мітки
            metric_part = parts[0]
            self.assertTrue(metric_part.startswith('system_'), f"Назва метрики має починатися з 'system_'")
            self.assertIn('{host="', metric_part, f"Метрика має містити мітку хоста")
            
            # Перевіряємо значення
            value_part = parts[1]
            self.assertTrue(value_part.replace('.', '').isdigit(), f"Значення має бути числом")

    # Тест обробки помилок мережі
    @patch('requests.get')
    def test_network_error_handling(self, mock_requests):
        # Мокування невдалого мережевого запиту
        mock_requests.side_effect = requests.RequestException()

        # Отримуємо метрики
        metrics = collect_metrics()
        # Перевіряємо мітку затримки мережі з -1.00 при помилці
        self.assertTrue(any('system_network_latency_ms{host=' in metric and '-1.00' in metric 
                          for metric in metrics.split('\n')))

    # Тест ендпоінта метрик
    def test_metrics_endpoint(self):
        # Виконуємо GET-запит до ендпоінта
        response = self.app.get('/metrics')
        self.assertEqual(response.status_code, 200)  # Перевіряємо статус-код 200
        self.assertEqual(response.mimetype, 'text/plain')  # Перевіряємо MIME-тип

    # Тест лічильника запитів
    def test_request_counter(self):
        # Тестуємо інкрементацію лічильника запитів
        initial_response = self.app.get('/metrics')
        initial_metrics = initial_response.data.decode()
        initial_count = int([m for m in initial_metrics.split('\n') 
                           if 'system_server_request_count' in m][0].split()[-1])

        # Виконуємо ще один запит
        second_response = self.app.get('/metrics')
        second_metrics = second_response.data.decode()
        second_count = int([m for m in second_metrics.split('\n') 
                          if 'system_server_request_count' in m][0].split()[-1])

        self.assertEqual(second_count, initial_count + 1)  # Перевіряємо, чи лічильник збільшився на 1

if __name__ == '__main__':
    unittest.main()  # Запускаємо всі тести
