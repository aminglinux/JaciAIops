#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 4: 使用 DeepLog 模型进行异常检测

功能：
1. 加载训练好的 DeepLog 模型
2. 模拟实时日志流
3. 使用滑动窗口预测下一个事件
4. 检测异常并输出结果

异常检测原理：
- 对于当前窗口的日志序列，模型预测下一个最可能出现的 Top-k 个事件
- 如果实际发生的事件不在 Top-k 预测列表中，则判定为异常
- 这种方法能够检测出偏离正常模式的日志序列
"""

import os
import torch
import torch.nn.functional as F
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import deque

# 导入 DeepLog 模型定义
from importlib import util as importlib_util
spec = importlib_util.spec_from_file_location("train_model", 
    Path(__file__).parent / "3_train_model.py")
train_module = importlib_util.module_from_spec(spec)
spec.loader.exec_module(train_module)
DeepLog = train_module.DeepLog


class DeepLogAnomalyDetector:
    """
    DeepLog 异常检测器
    
    使用训练好的 DeepLog 模型检测日志序列中的异常
    """
    
    def __init__(self, model_path='models/deeplog_model.pth', top_k=3):
        """
        初始化异常检测器
        
        Args:
            model_path: 模型文件路径
            top_k: 预测的 Top-k 个事件
        """
        self.model_path = Path(model_path)
        self.top_k = top_k
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        self.model = None
        self.event2idx = None
        self.idx2event = None
        self.num_events = None
        self.window_size = None
        
        self.stats = {
            'total_logs': 0,
            'total_predictions': 0,
            'anomalies_detected': 0,
            'normal_logs': 0
        }
    
    def load_model(self):
        """
        加载训练好的模型
        
        Returns:
            bool: 是否加载成功
        """
        print(f"{'='*80}")
        print(f"加载 DeepLog 模型")
        print(f"{'='*80}\n")
        
        if not self.model_path.exists():
            print(f"❌ 错误: 模型文件不存在: {self.model_path}")
            print(f"请先运行 3_train_model.py 训练模型")
            return False
        
        print(f"📂 加载模型: {self.model_path}")
        
        # 加载模型检查点
        checkpoint = torch.load(self.model_path, map_location=self.device)
        
        # 提取模型配置
        self.event2idx = checkpoint['event2idx']
        self.idx2event = checkpoint['idx2event']
        self.num_events = checkpoint['num_events']
        self.window_size = checkpoint['window_size']
        
        print(f"   - 事件类型数: {self.num_events}")
        print(f"   - 窗口大小: {self.window_size}")
        
        # 创建模型
        self.model = DeepLog(
            num_events=self.num_events,
            embedding_dim=128,
            hidden_dim=128,
            num_layers=2,
            dropout=0.3
        ).to(self.device)
        
        # 加载模型权重
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()
        
        print(f"   - 设备: {self.device}")
        print(f"   - 模型加载成功！\n")
        
        return True
    
    def load_test_data(self, data_path='data/cleaned/logs_structured.csv', test_ratio=0.3):
        """
        加载测试数据（模拟实时日志流）
        
        Args:
            data_path: 数据文件路径
            test_ratio: 测试数据比例
            
        Returns:
            DataFrame: 测试数据
        """
        print(f"{'='*80}")
        print(f"加载测试数据")
        print(f"{'='*80}\n")
        
        data_file = Path(data_path)
        
        if not data_file.exists():
            raise FileNotFoundError(f"数据文件不存在: {data_file}\n请先运行 2_parse_logs.py 生成结构化日志")
        
        print(f"📂 加载数据: {data_file}")
        df = pd.read_csv(data_file)
        
        # 取后半部分作为测试数据（模拟实时日志流）
        split_idx = int(len(df) * (1 - test_ratio))
        df_test = df.iloc[split_idx:].reset_index(drop=True)
        
        print(f"   - 总日志数: {len(df)}")
        print(f"   - 测试日志数: {len(df_test)}")
        print(f"   - 测试数据比例: {test_ratio*100}%")
        print(f"   - 时间范围: {df_test['Timestamp'].iloc[0]} ~ {df_test['Timestamp'].iloc[-1]}\n")
        
        return df_test
    
    def predict_next_events(self, sequence):
        """
        预测下一个最可能出现的 Top-k 个事件
        
        Args:
            sequence: 当前窗口的事件序列（EventId 列表）
            
        Returns:
            list: Top-k 个预测事件的 EventId
            list: Top-k 个预测事件的概率
        """
        # 将 EventId 转换为索引
        sequence_indices = [self.event2idx.get(eid, 0) for eid in sequence]
        
        # 转换为张量
        sequence_tensor = torch.LongTensor([sequence_indices]).to(self.device)
        
        # 预测
        with torch.no_grad():
            outputs = self.model(sequence_tensor)
            probabilities = F.softmax(outputs, dim=1)
            
            # 获取 Top-k 个预测
            top_k_probs, top_k_indices = torch.topk(probabilities, self.top_k, dim=1)
            
            # 转换为 EventId
            top_k_events = [self.idx2event[idx.item()] for idx in top_k_indices[0]]
            top_k_probs = top_k_probs[0].cpu().numpy()
        
        return top_k_events, top_k_probs
    
    def detect_anomalies(self, df_test):
        """
        检测异常
        
        Args:
            df_test: 测试数据 DataFrame
            
        Returns:
            list: 异常列表
        """
        print(f"{'='*80}")
        print(f"开始异常检测")
        print(f"{'='*80}\n")
        
        print(f"配置:")
        print(f"  - 窗口大小: {self.window_size}")
        print(f"  - Top-k: {self.top_k}")
        print(f"  - 异常判定: 实际事件不在 Top-{self.top_k} 预测列表中\n")
        
        anomalies = []
        
        # 使用滑动窗口遍历测试数据
        event_ids = df_test['EventId'].tolist()
        timestamps = df_test['Timestamp'].tolist()
        templates = df_test['EventTemplate'].tolist()
        
        # 使用 deque 维护滑动窗口
        window = deque(maxlen=self.window_size)
        
        print(f"开始处理日志流...\n")
        
        for i in range(len(event_ids)):
            current_event = event_ids[i]
            current_timestamp = timestamps[i]
            current_template = templates[i]
            
            self.stats['total_logs'] += 1
            
            # 如果窗口已满，进行预测
            if len(window) == self.window_size:
                # 预测下一个事件
                predicted_events, predicted_probs = self.predict_next_events(list(window))
                
                self.stats['total_predictions'] += 1
                
                # 判断是否为异常
                if current_event not in predicted_events:
                    # 检测到异常
                    anomaly = {
                        'timestamp': current_timestamp,
                        'expected_events': predicted_events,
                        'expected_probs': predicted_probs,
                        'actual_event': current_event,
                        'actual_template': current_template,
                        'window': list(window)
                    }
                    anomalies.append(anomaly)
                    self.stats['anomalies_detected'] += 1
                    
                    # 输出异常信息
                    print(f"[ANOMALY DETECTED] Time: {current_timestamp}")
                    print(f"  Expected Top-{self.top_k}: {predicted_events}")
                    print(f"  Probabilities: {[f'{p:.4f}' for p in predicted_probs]}")
                    print(f"  Actual: {current_event} ({current_template})")
                    print(f"  Window: {list(window)}")
                    print()
                else:
                    self.stats['normal_logs'] += 1
            
            # 更新窗口
            window.append(current_event)
        
        return anomalies
    
    def print_statistics(self, anomalies):
        """
        打印统计信息
        
        Args:
            anomalies: 异常列表
        """
        print(f"{'='*80}")
        print(f"检测完成！")
        print(f"{'='*80}\n")
        
        print(f"统计信息:")
        print(f"  总日志数: {self.stats['total_logs']}")
        print(f"  总预测次数: {self.stats['total_predictions']}")
        print(f"  检测到的异常数: {self.stats['anomalies_detected']}")
        print(f"  正常日志数: {self.stats['normal_logs']}")
        
        if self.stats['total_predictions'] > 0:
            anomaly_rate = self.stats['anomalies_detected'] / self.stats['total_predictions'] * 100
            print(f"  异常率: {anomaly_rate:.2f}%")
        
        # 分析异常类型
        if anomalies:
            print(f"\n异常事件统计:")
            anomaly_events = {}
            for anomaly in anomalies:
                event = anomaly['actual_event']
                anomaly_events[event] = anomaly_events.get(event, 0) + 1
            
            for event, count in sorted(anomaly_events.items(), key=lambda x: x[1], reverse=True):
                print(f"  {event}: {count} 次")
    
    def save_results(self, anomalies, output_file='reports/anomaly_detection_results.csv'):
        """
        保存检测结果
        
        Args:
            anomalies: 异常列表
            output_file: 输出文件路径
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"\n💾 保存检测结果到: {output_path}")
        
        # 转换为 DataFrame
        df_anomalies = pd.DataFrame([
            {
                'timestamp': a['timestamp'],
                'expected_events': '|'.join(a['expected_events']),
                'expected_probs': '|'.join([f'{p:.4f}' for p in a['expected_probs']]),
                'actual_event': a['actual_event'],
                'actual_template': a['actual_template'],
                'window': '|'.join(a['window'])
            }
            for a in anomalies
        ])
        
        # 保存为 CSV
        df_anomalies.to_csv(output_path, index=False)
        
        print(f"   - 保存成功！")
        print(f"   - 文件大小: {os.path.getsize(output_path) / 1024:.2f} KB")
    
    def detect(self):
        """
        主检测流程
        """
        print(f"\n{'='*80}")
        print(f"DeepLog 异常检测")
        print(f"{'='*80}\n")
        
        # 1. 加载模型
        if not self.load_model():
            return
        
        # 2. 加载测试数据
        df_test = self.load_test_data()
        
        # 3. 检测异常
        anomalies = self.detect_anomalies(df_test)
        
        # 4. 打印统计信息
        self.print_statistics(anomalies)
        
        # 5. 保存结果
        if anomalies:
            self.save_results(anomalies)
        
        return anomalies


def main():
    """
    主函数
    """
    detector = DeepLogAnomalyDetector(
        model_path='models/deeplog_model.pth',
        top_k=1
    )
    
    anomalies = detector.detect()
    
    if anomalies:
        print(f"\n✅ 检测完成！发现 {len(anomalies)} 个异常")
    else:
        print(f"\n✅ 检测完成！未发现异常")


if __name__ == '__main__':
    main()
