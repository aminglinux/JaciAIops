#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 3: 使用 DeepLog 模型进行日志序列学习

DeepLog 原理：
1. 将日志事件序列视为时间序列
2. 使用 LSTM 学习日志事件的正常模式
3. 通过预测下一个事件来检测异常
4. 如果预测的概率分布与实际事件差异较大，则认为是异常

模型结构：
- Embedding Layer: 将 EventId 转换为稠密向量
- LSTM Layer: 学习日志序列的时序模式
- Linear Layer: 将 LSTM 输出映射到事件空间
- Softmax: 输出每个事件的概率分布

训练流程：
1. 加载结构化日志数据
2. 构建滑动窗口序列
3. 训练 LSTM 模型
4. 保存训练好的模型
"""

import os
import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split
from torch.utils.data import Dataset, DataLoader
from collections import Counter


class LogSequenceDataset(Dataset):
    """
    日志序列数据集
    
    使用滑动窗口方法构建训练数据：
    - 输入 X: 前 window_size 个 EventId
    - 标签 Y: 第 window_size + 1 个 EventId
    """
    
    def __init__(self, sequences, labels):
        """
        初始化数据集
        
        Args:
            sequences: 输入序列列表
            labels: 标签列表
        """
        self.sequences = torch.LongTensor(sequences)
        self.labels = torch.LongTensor(labels)
    
    def __len__(self):
        return len(self.sequences)
    
    def __getitem__(self, idx):
        return self.sequences[idx], self.labels[idx]


class DeepLog(nn.Module):
    """
    DeepLog 模型
    
    结构：
    1. Embedding Layer: 将 EventId 转换为稠密向量
    2. LSTM Layer: 学习日志序列的时序模式
    3. Linear Layer: 将 LSTM 输出映射到事件空间
    4. Softmax: 输出每个事件的概率分布
    
    原理：
    - LSTM 能够捕捉长期依赖关系
    - 通过学习正常日志序列的模式
    - 预测下一个可能的日志事件
    - 如果实际事件不在预测的 top-k 个事件中，则认为是异常
    """
    
    def __init__(self, num_events, embedding_dim=128, hidden_dim=128, num_layers=2, dropout=0.3):
        """
        初始化 DeepLog 模型
        
        Args:
            num_events: 事件总数（词汇表大小）
            embedding_dim: Embedding 维度
            hidden_dim: LSTM 隐藏层维度
            num_layers: LSTM 层数
            dropout: Dropout 概率
        """
        super(DeepLog, self).__init__()
        
        self.num_events = num_events
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        
        # Embedding Layer: 将 EventId 转换为稠密向量
        # 输入: [batch_size, seq_len] (EventId 序列)
        # 输出: [batch_size, seq_len, embedding_dim]
        self.embedding = nn.Embedding(num_events, embedding_dim)
        
        # LSTM Layer: 学习日志序列的时序模式
        # 输入: [batch_size, seq_len, embedding_dim]
        # 输出: [batch_size, seq_len, hidden_dim]
        self.lstm = nn.LSTM(
            input_size=embedding_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0
        )
        
        # Linear Layer: 将 LSTM 输出映射到事件空间
        # 输入: [batch_size, hidden_dim]
        # 输出: [batch_size, num_events]
        self.fc = nn.Linear(hidden_dim, num_events)
        
        # Dropout Layer: 防止过拟合
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x):
        """
        前向传播
        
        Args:
            x: 输入序列 [batch_size, seq_len]
            
        Returns:
            输出概率分布 [batch_size, num_events]
        """
        # Embedding: [batch_size, seq_len] -> [batch_size, seq_len, embedding_dim]
        x = self.embedding(x)
        
        # LSTM: [batch_size, seq_len, embedding_dim] -> [batch_size, seq_len, hidden_dim]
        lstm_out, _ = self.lstm(x)
        
        # 取最后一个时间步的输出: [batch_size, seq_len, hidden_dim] -> [batch_size, hidden_dim]
        lstm_out = lstm_out[:, -1, :]
        
        # Dropout
        lstm_out = self.dropout(lstm_out)
        
        # Linear: [batch_size, hidden_dim] -> [batch_size, num_events]
        output = self.fc(lstm_out)
        
        return output


class DeepLogTrainer:
    """
    DeepLog 训练器
    
    负责数据预处理、模型训练和评估
    """
    
    def __init__(self, input_dir='data/cleaned', output_dir='models', window_size=10):
        """
        初始化训练器
        
        Args:
            input_dir: 输入目录
            output_dir: 输出目录
            window_size: 滑动窗口大小
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.window_size = window_size
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        self.event2idx = {}
        self.idx2event = {}
        self.num_events = 0
        
        self.stats = {
            'total_sequences': 0,
            'train_sequences': 0,
            'val_sequences': 0,
            'num_events': 0,
            'best_val_loss': float('inf')
        }
    
    def load_data(self):
        """
        加载结构化日志数据
        
        Returns:
            DataFrame: 包含 EventId 列的数据
        """
        input_file = self.input_dir / 'logs_structured.csv'
        
        if not input_file.exists():
            raise FileNotFoundError(f"输入文件不存在: {input_file}\n请先运行 2_parse_logs.py 生成结构化日志")
        
        print(f"📂 加载结构化日志: {input_file}")
        df = pd.read_csv(input_file)
        
        print(f"   - 总日志数: {len(df)}")
        print(f"   - 列: {df.columns.tolist()}")
        
        return df
    
    def build_vocabulary(self, event_ids):
        """
        构建事件词汇表
        
        Args:
            event_ids: EventId 列表
        """
        print(f"\n🔧 构建事件词汇表...")
        
        # 统计每个事件的出现次数
        event_counts = Counter(event_ids)
        
        # 创建 EventId 到索引的映射
        # 索引 0 保留给未知事件（UNK）
        self.event2idx = {'UNK': 0}
        self.idx2event = {0: 'UNK'}
        
        idx = 1
        for event_id in event_counts.keys():
            self.event2idx[event_id] = idx
            self.idx2event[idx] = event_id
            idx += 1
        
        self.num_events = len(self.event2idx)
        self.stats['num_events'] = self.num_events
        
        print(f"   - 事件类型数: {self.num_events}")
        print(f"   - 前 5 个事件: {list(self.event2idx.keys())[:5]}")
    
    def build_sequences(self, event_ids):
        """
        使用滑动窗口构建训练序列
        
        Args:
            event_ids: EventId 列表
            
        Returns:
            sequences: 输入序列列表
            labels: 标签列表
        """
        print(f"\n🔧 构建滑动窗口序列...")
        print(f"   - 窗口大小: {self.window_size}")
        
        # 将 EventId 转换为索引
        event_indices = [self.event2idx.get(eid, 0) for eid in event_ids]
        
        sequences = []
        labels = []
        
        # 使用滑动窗口构建序列
        for i in range(len(event_indices) - self.window_size):
            # 输入: 前 window_size 个事件
            seq = event_indices[i:i + self.window_size]
            # 标签: 第 window_size + 1 个事件
            label = event_indices[i + self.window_size]
            
            sequences.append(seq)
            labels.append(label)
        
        self.stats['total_sequences'] = len(sequences)
        
        print(f"   - 总序列数: {len(sequences)}")
        print(f"   - 序列长度: {self.window_size}")
        
        return sequences, labels
    
    def create_dataloaders(self, sequences, labels, batch_size=64, val_split=0.2):
        """
        创建训练和验证数据加载器
        
        Args:
            sequences: 输入序列列表
            labels: 标签列表
            batch_size: 批次大小
            val_split: 验证集比例
            
        Returns:
            train_loader: 训练数据加载器
            val_loader: 验证数据加载器
        """
        print(f"\n🔧 创建数据加载器...")
        print(f"   - 批次大小: {batch_size}")
        print(f"   - 验证集比例: {val_split}")
        
        # 划分训练集和验证集
        train_seq, val_seq, train_labels, val_labels = train_test_split(
            sequences, labels, test_size=val_split, random_state=42
        )
        
        self.stats['train_sequences'] = len(train_seq)
        self.stats['val_sequences'] = len(val_seq)
        
        print(f"   - 训练序列数: {len(train_seq)}")
        print(f"   - 验证序列数: {len(val_seq)}")
        
        # 创建数据集
        train_dataset = LogSequenceDataset(train_seq, train_labels)
        val_dataset = LogSequenceDataset(val_seq, val_labels)
        
        # 创建数据加载器
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        
        return train_loader, val_loader
    
    def train_model(self, train_loader, val_loader, num_epochs=10, learning_rate=0.001):
        """
        训练 DeepLog 模型
        
        Args:
            train_loader: 训练数据加载器
            val_loader: 验证数据加载器
            num_epochs: 训练轮数
            learning_rate: 学习率
            
        Returns:
            model: 训练好的模型
        """
        print(f"\n{'='*80}")
        print(f"开始训练 DeepLog 模型")
        print(f"{'='*80}")
        print(f"设备: {self.device}")
        print(f"训练轮数: {num_epochs}")
        print(f"学习率: {learning_rate}")
        print(f"{'='*80}\n")
        
        # 创建模型
        model = DeepLog(
            num_events=self.num_events,
            embedding_dim=128,
            hidden_dim=128,
            num_layers=2,
            dropout=0.3
        ).to(self.device)
        
        # 定义损失函数和优化器
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(model.parameters(), lr=learning_rate)
        
        # 训练循环
        for epoch in range(num_epochs):
            # 训练阶段
            model.train()
            train_loss = 0.0
            train_correct = 0
            train_total = 0
            
            for batch_sequences, batch_labels in train_loader:
                batch_sequences = batch_sequences.to(self.device)
                batch_labels = batch_labels.to(self.device)
                
                # 前向传播
                optimizer.zero_grad()
                outputs = model(batch_sequences)
                loss = criterion(outputs, batch_labels)
                
                # 反向传播
                loss.backward()
                optimizer.step()
                
                # 统计
                train_loss += loss.item()
                _, predicted = torch.max(outputs.data, 1)
                train_total += batch_labels.size(0)
                train_correct += (predicted == batch_labels).sum().item()
            
            train_loss /= len(train_loader)
            train_acc = train_correct / train_total
            
            # 验证阶段
            model.eval()
            val_loss = 0.0
            val_correct = 0
            val_total = 0
            
            with torch.no_grad():
                for batch_sequences, batch_labels in val_loader:
                    batch_sequences = batch_sequences.to(self.device)
                    batch_labels = batch_labels.to(self.device)
                    
                    outputs = model(batch_sequences)
                    loss = criterion(outputs, batch_labels)
                    
                    val_loss += loss.item()
                    _, predicted = torch.max(outputs.data, 1)
                    val_total += batch_labels.size(0)
                    val_correct += (predicted == batch_labels).sum().item()
            
            val_loss /= len(val_loader)
            val_acc = val_correct / val_total
            
            # 打印训练信息
            print(f"Epoch [{epoch+1}/{num_epochs}]")
            print(f"  训练 - Loss: {train_loss:.4f}, Acc: {train_acc:.4f}")
            print(f"  验证 - Loss: {val_loss:.4f}, Acc: {val_acc:.4f}")
            
            # 保存最佳模型
            if val_loss < self.stats['best_val_loss']:
                self.stats['best_val_loss'] = val_loss
                self.save_model(model, 'deeplog_model_best.pth')
                print(f"  ✓ 保存最佳模型 (验证损失: {val_loss:.4f})")
            
            print()
        
        return model
    
    def save_model(self, model, filename):
        """
        保存模型
        
        Args:
            model: 训练好的模型
            filename: 文件名
        """
        output_file = self.output_dir / filename
        
        torch.save({
            'model_state_dict': model.state_dict(),
            'event2idx': self.event2idx,
            'idx2event': self.idx2event,
            'num_events': self.num_events,
            'window_size': self.window_size,
            'stats': self.stats
        }, output_file)
        
        print(f"💾 模型已保存到: {output_file}")
    
    def train(self):
        """
        主训练流程
        """
        print(f"\n{'='*80}")
        print(f"DeepLog 模型训练")
        print(f"{'='*80}\n")
        
        # 1. 加载数据
        df = self.load_data()
        
        # 2. 构建词汇表
        event_ids = df['EventId'].tolist()
        self.build_vocabulary(event_ids)
        
        # 3. 构建序列
        sequences, labels = self.build_sequences(event_ids)
        
        # 4. 创建数据加载器
        train_loader, val_loader = self.create_dataloaders(sequences, labels)
        
        # 5. 训练模型
        model = self.train_model(train_loader, val_loader, num_epochs=10)
        
        # 6. 保存最终模型
        self.save_model(model, 'deeplog_model.pth')
        
        # 7. 打印统计信息
        print(f"\n{'='*80}")
        print(f"训练完成！")
        print(f"{'='*80}")
        print(f"\n统计信息:")
        print(f"  总序列数: {self.stats['total_sequences']}")
        print(f"  训练序列数: {self.stats['train_sequences']}")
        print(f"  验证序列数: {self.stats['val_sequences']}")
        print(f"  事件类型数: {self.stats['num_events']}")
        print(f"  最佳验证损失: {self.stats['best_val_loss']:.4f}")
        
        return model


def main():
    """
    主函数
    """
    trainer = DeepLogTrainer(
        input_dir='data/cleaned',
        output_dir='models',
        window_size=10
    )
    
    model = trainer.train()
    
    print(f"\n✅ 训练完成！模型已保存到 models/deeplog_model.pth")


if __name__ == '__main__':
    main()
