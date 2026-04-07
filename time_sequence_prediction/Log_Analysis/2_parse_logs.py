#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 2: 使用简单方法解析日志

功能：
1. 读取 logs_raw.log 文件
2. 使用正则表达式提取时间戳、级别和消息内容
3. 使用简单的模板提取方法
4. 将解析结果保存为 logs_structured.csv
5. 打印前 5 个日志模板
"""

import os
import re
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import Counter


class SimpleLogParser:
    """
    简单的日志解析器
    
    使用简单的模板提取方法，不依赖 logparser 库
    """
    
    def __init__(self, input_dir='data/raw', output_dir='data/cleaned'):
        """
        初始化日志解析器
        
        Args:
            input_dir: 输入目录
            output_dir: 输出目录
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_format = r'\[(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\] \[(?P<level>\w+)\] \[(?P<service>[\w-]+)\] (?P<message>.+)'
        
        self.stats = {
            'total_logs': 0,
            'unique_events': 0,
            'info_logs': 0,
            'error_logs': 0,
            'warn_logs': 0
        }
    
    def extract_template(self, message):
        """
        从消息中提取模板
        
        将数字、IP地址等动态参数替换为占位符
        
        Args:
            message: 日志消息
            
        Returns:
            str: 日志模板
        """
        template = message
        
        template = re.sub(r'\b\d+\.\d+\.\d+\.\d+\b', '<IP>', template)
        
        template = re.sub(r'\b\d+ms\b', '<TIME>', template)
        template = re.sub(r'\b\d+s\b', '<TIME>', template)
        template = re.sub(r'\b\d+ms\.\d+\b', '<TIME>', template)
        
        template = re.sub(r'\b\d+\b', '<NUM>', template)
        
        template = re.sub(r'\b[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b', '<ID>', template)
        
        return template
    
    def parse_logs(self, input_file):
        """
        解析日志文件
        
        Args:
            input_file: 输入日志文件
            
        Returns:
            DataFrame: 解析后的日志数据
        """
        print(f"\n{'='*80}")
        print(f"日志解析 - 简单模板提取")
        print(f"{'='*80}")
        print(f"📂 读取日志文件: {input_file}")
        
        logs = []
        templates = {}
        event_counter = Counter()
        
        with open(input_file, 'r', encoding='utf-8') as f:
            for line_id, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                match = re.match(self.log_format, line)
                if match:
                    timestamp = match.group('timestamp')
                    level = match.group('level')
                    service = match.group('service')
                    message = match.group('message')
                    
                    template = self.extract_template(message)
                    
                    if template not in templates:
                        event_id = f"E{len(templates) + 1}"
                        templates[template] = event_id
                    else:
                        event_id = templates[template]
                    
                    logs.append({
                        'LineId': line_id,
                        'EventId': event_id,
                        'EventTemplate': template,
                        'Timestamp': timestamp,
                        'Level': level,
                        'Service': service,
                        'Message': message
                    })
                    
                    event_counter[event_id] += 1
                    self.stats['total_logs'] += 1
                    
                    if level == 'INFO':
                        self.stats['info_logs'] += 1
                    elif level == 'ERROR':
                        self.stats['error_logs'] += 1
                    elif level == 'WARN':
                        self.stats['warn_logs'] += 1
        
        self.stats['unique_events'] = len(templates)
        
        print(f"   - 总日志数: {self.stats['total_logs']}")
        print(f"   - INFO 日志: {self.stats['info_logs']}")
        print(f"   - ERROR 日志: {self.stats['error_logs']}")
        print(f"   - WARN 日志: {self.stats['warn_logs']}")
        print(f"   - 提取的事件模板数: {self.stats['unique_events']}")
        
        return pd.DataFrame(logs), templates, event_counter
    
    def save_results(self, df, output_file):
        """
        保存解析结果
        
        Args:
            df: 解析后的数据
            output_file: 输出文件
        """
        print(f"\n💾 保存解析结果到: {output_file}")
        
        df.to_csv(output_file, index=False)
        
        file_size = os.path.getsize(output_file) / 1024
        
        print(f"   - 保存成功！")
        print(f"   - 文件大小: {file_size:.2f} KB")
    
    def print_top_templates(self, templates, event_counter, top_n=5):
        """
        打印前 N 个日志模板
        
        Args:
            templates: 模板字典
            event_counter: 事件计数器
            top_n: 前N个
        """
        print(f"\n📊 前 {top_n} 个日志模板:")
        print(f"{'='*80}")
        
        top_events = event_counter.most_common(top_n)
        
        template_to_event = {v: k for k, v in templates.items()}
        
        for i, (event_id, count) in enumerate(top_events, 1):
            template = template_to_event[event_id]
            print(f"\n模板 {i}:")
            print(f"  EventId: {event_id}")
            print(f"  模板: {template}")
            print(f"  出现次数: {count}")
    
    def parse(self):
        """
        主解析流程
        """
        input_file = self.input_dir / 'logs_raw.log'
        
        if not input_file.exists():
            print(f"❌ 错误: 输入文件不存在: {input_file}")
            print(f"请先运行 1_generate_data.py 生成日志数据")
            return
        
        df, templates, event_counter = self.parse_logs(input_file)
        
        output_file = self.output_dir / 'logs_structured.csv'
        self.save_results(df, output_file)
        
        self.print_top_templates(templates, event_counter)
        
        print(f"\n{'='*80}")
        print(f"解析完成！")
        print(f"{'='*80}")
        print(f"\n统计信息:")
        print(f"  总日志数: {self.stats['total_logs']}")
        print(f"  事件模板数: {self.stats['unique_events']}")
        print(f"  INFO 日志: {self.stats['info_logs']}")
        print(f"  ERROR 日志: {self.stats['error_logs']}")
        print(f"  WARN 日志: {self.stats['warn_logs']}")


def main():
    """
    主函数
    """
    parser = SimpleLogParser(
        input_dir='data/raw',
        output_dir='data/cleaned'
    )
    
    parser.parse()
    
    print(f"\n✅ 解析完成！结果已保存到 data/cleaned/logs_structured.csv")


if __name__ == '__main__':
    main()
