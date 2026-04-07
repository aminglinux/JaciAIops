#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 1: 生成模拟微服务日志数据

功能：
1. 模拟订单流程日志：Receive Request -> Query Database -> Validate User -> Create Order -> Return Response
2. 正常模式：大部分为 INFO 级别，符合正常序列
3. 异常模式A：高并发时段插入 "Connection Timeout" 错误
4. 异常模式B：Validate User 失败后直接 System Rollback
5. 生成约 5000 行日志数据
"""

import os
import random
from datetime import datetime, timedelta
from pathlib import Path


class LogDataGenerator:
    """
    微服务日志数据生成器
    模拟订单处理流程的各种日志模式
    """
    
    def __init__(self, output_dir='data/raw', target_lines=5000):
        """
        初始化日志生成器
        
        Args:
            output_dir: 输出目录
            target_lines: 目标日志行数
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.target_lines = target_lines
        
        self.normal_flow = [
            ('INFO', 'order-service', 'Receive Request'),
            ('INFO', 'database-service', 'Query Database'),
            ('INFO', 'auth-service', 'Validate User'),
            ('INFO', 'order-service', 'Create Order'),
            ('INFO', 'order-service', 'Return Response')
        ]
        
        self.anomaly_b_flow = [
            ('INFO', 'order-service', 'Receive Request'),
            ('INFO', 'database-service', 'Query Database'),
            ('ERROR', 'auth-service', 'Validate User Failed'),
            ('WARN', 'order-service', 'System Rollback')
        ]
        
        self.services = ['order-service', 'database-service', 'auth-service', 'payment-service', 'inventory-service']
        
        self.stats = {
            'total_logs': 0,
            'normal_logs': 0,
            'anomaly_a_logs': 0,
            'anomaly_b_logs': 0,
            'info_logs': 0,
            'error_logs': 0,
            'warn_logs': 0
        }
    
    def _generate_timestamp(self, base_time, offset_seconds):
        """
        生成时间戳
        
        Args:
            base_time: 基准时间
            offset_seconds: 偏移秒数
            
        Returns:
            格式化的时间戳字符串
        """
        timestamp = base_time + timedelta(seconds=offset_seconds)
        return timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    
    def _is_high_concurrency_period(self, hour):
        """
        判断是否为高并发时段
        高并发时段：10:00-12:00, 14:00-16:00, 20:00-22:00
        
        Args:
            hour: 小时
            
        Returns:
            bool: 是否为高并发时段
        """
        return (10 <= hour < 12) or (14 <= hour < 16) or (20 <= hour < 22)
    
    def _generate_normal_flow(self, base_time, offset_seconds):
        """
        生成正常流程日志
        
        Args:
            base_time: 基准时间
            offset_seconds: 偏移秒数
            
        Returns:
            list: 日志列表
        """
        logs = []
        for i, (level, service, message) in enumerate(self.normal_flow):
            timestamp = self._generate_timestamp(base_time, offset_seconds + i * 0.1)
            log_line = f"[{timestamp}] [{level}] [{service}] {message}\n"
            logs.append(log_line)
            self.stats['normal_logs'] += 1
            if level == 'INFO':
                self.stats['info_logs'] += 1
        return logs
    
    def _generate_anomaly_a(self, base_time, offset_seconds):
        """
        生成异常模式A：突发错误（Connection Timeout）
        在高并发时段插入连接超时错误
        
        Args:
            base_time: 基准时间
            offset_seconds: 偏移秒数
            
        Returns:
            list: 日志列表
        """
        logs = []
        
        logs.extend(self._generate_normal_flow(base_time, offset_seconds))
        
        timeout_offset = offset_seconds + random.uniform(0.5, 2.0)
        timestamp = self._generate_timestamp(base_time, timeout_offset)
        timeout_log = f"[{timestamp}] [ERROR] [database-service] Connection Timeout\n"
        logs.append(timeout_log)
        
        self.stats['anomaly_a_logs'] += 1
        self.stats['error_logs'] += 1
        
        return logs
    
    def _generate_anomaly_b(self, base_time, offset_seconds):
        """
        生成异常模式B：序列异常
        Validate User 失败后直接 System Rollback
        
        Args:
            base_time: 基准时间
            offset_seconds: 偏移秒数
            
        Returns:
            list: 日志列表
        """
        logs = []
        for i, (level, service, message) in enumerate(self.anomaly_b_flow):
            timestamp = self._generate_timestamp(base_time, offset_seconds + i * 0.1)
            log_line = f"[{timestamp}] [{level}] [{service}] {message}\n"
            logs.append(log_line)
            
            if level == 'ERROR':
                self.stats['error_logs'] += 1
            elif level == 'WARN':
                self.stats['warn_logs'] += 1
            else:
                self.stats['info_logs'] += 1
        
        self.stats['anomaly_b_logs'] += 1
        
        return logs
    
    def generate_logs(self):
        """
        生成日志数据
        
        Returns:
            str: 输出文件路径
        """
        print("开始生成日志数据...")
        print(f"目标日志行数: {self.target_lines}")
        
        all_logs = []
        base_time = datetime(2024, 1, 1, 0, 0, 0)
        current_offset = 0
        
        while len(all_logs) < self.target_lines:
            current_time = base_time + timedelta(seconds=current_offset)
            hour = current_time.hour
            
            is_high_concurrency = self._is_high_concurrency_period(hour)
            
            if is_high_concurrency:
                anomaly_a_prob = 0.30
                anomaly_b_prob = 0.20
            else:
                anomaly_a_prob = 0.10
                anomaly_b_prob = 0.05
            
            rand = random.random()
            
            if rand < anomaly_a_prob:
                logs = self._generate_anomaly_a(base_time, current_offset)
            elif rand < anomaly_a_prob + anomaly_b_prob:
                logs = self._generate_anomaly_b(base_time, current_offset)
            else:
                logs = self._generate_normal_flow(base_time, current_offset)
            
            all_logs.extend(logs)
            
            current_offset += random.uniform(1.0, 5.0)
        
        all_logs = all_logs[:self.target_lines]
        
        output_file = self.output_dir / 'logs_raw.log'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.writelines(all_logs)
        
        self.stats['total_logs'] = len(all_logs)
        
        print(f"\n日志生成完成！")
        print(f"输出文件: {output_file}")
        print(f"\n统计信息:")
        print(f"  总日志数: {self.stats['total_logs']}")
        print(f"  正常日志: {self.stats['normal_logs']}")
        print(f"  异常A日志: {self.stats['anomaly_a_logs']}")
        print(f"  异常B日志: {self.stats['anomaly_b_logs']}")
        print(f"  INFO 日志: {self.stats['info_logs']}")
        print(f"  ERROR 日志: {self.stats['error_logs']}")
        print(f"  WARN 日志: {self.stats['warn_logs']}")
        
        return str(output_file)


def main():
    """
    主函数
    """
    generator = LogDataGenerator(
        output_dir='data/raw',
        target_lines=5000
    )
    
    output_file = generator.generate_logs()
    
    print(f"\n日志文件已保存到: {output_file}")
    print(f"\n示例日志（前 10 行）:")
    with open(output_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 10:
                break
            print(f"  {line.rstrip()}")


if __name__ == '__main__':
    main()