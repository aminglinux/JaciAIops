# 阿里云 OSS 诊断技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `OSS`, `对象存储`, `Bucket`, `上传失败`
- `权限`, `STS`, `签名URL`, `跨域`, `CORS`
- `生命周期`, `存储类型`, `低频`, `归档`
- `CDN`, `加速`, `回源`, `防盗链`

### 1.2 适用条件
- OSS 上传/下载失败
- 权限配置问题 (403)
- CORS 跨域问题
- 存储成本优化
- 数据迁移/同步

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 确认 Bucket 信息                                   │
│  - Bucket 名称 / 区域                                      │
│  - 存储类型 / 访问权限                                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Bucket 状态检查                                    │
│  - 访问权限 (ACL)                                           │
│  - 存储类型                                                 │
│  - 用量统计                                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 权限与策略检查                                     │
│  - Bucket Policy                                            │
│  - RAM 授权                                                 │
│  - STS 临时凭证                                             │
│  - CORS 配置                                                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 上传/下载诊断                                      │
│  - 网络连通性                                               │
│  - 签名/认证                                                │
│  - 大小限制                                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 定位问题并提供解决方案                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 Bucket 管理

```bash
# 列出所有 Bucket
aliyun oss ls

# 查看 Bucket 信息
aliyun oss ls oss://<bucket_name> --limited-num 10

# 查看 Bucket ACL
aliyun oss bucket-acl --method get oss://<bucket_name>

# 查看 Bucket 信息 (API)
aliyun oss GetBucketAcl --BucketName <bucket_name>

# 查看 Bucket 用量
aliyun oss ls oss://<bucket_name> --limited-num 0 -s

# 查看存储类型
aliyun oss bucket-storage-class --method get oss://<bucket_name>
```

### 3.2 权限检查

```bash
# 查看 Bucket Policy
aliyun oss bucket-policy --method get oss://<bucket_name>

# 查看 CORS 配置
aliyun oss cors --method get oss://<bucket_name>

# 查看 Referer 防盗链
aliyun oss referer --method get oss://<bucket_name>

# 查看 RAM 用户权限
aliyun ram ListPoliciesForUser --UserName <user_name>

# 测试上传权限
aliyun oss cp /tmp/test.txt oss://<bucket_name>/test.txt

# 测试下载权限
aliyun oss cp oss://<bucket_name>/test.txt /tmp/test_download.txt
```

### 3.3 生命周期与成本

```bash
# 查看生命周期规则
aliyun oss lifecycle --method get oss://<bucket_name>

# 查看存储类型分布
aliyun oss ls oss://<bucket_name> -s | awk '{print $4}' | sort | uniq -c

# 查看 Bucket 统计信息
aliyun oss stat oss://<bucket_name>

# 查看对象元数据
aliyun oss stat oss://<bucket_name>/<object_key>
```

### 3.4 上传/下载诊断

```bash
# 测试上传 (小文件)
echo "test" > /tmp/test.txt
aliyun oss cp /tmp/test.txt oss://<bucket_name>/test.txt

# 测试分片上传 (大文件)
aliyun oss cp /tmp/large_file.tar.gz oss://<bucket_name>/ --part-size 10485760

# 测试下载速度
time aliyun oss cp oss://<bucket_name>/test.txt /tmp/test_download.txt

# 测试 OSS 端点连通性
curl -I https://<bucket_name>.oss-cn-hangzhou.aliyuncs.com

# 查看签名 URL
aliyun oss sign oss://<bucket_name>/<object_key> --timeout 3600
```

---

## 4. 常见问题与解决方案

### 4.1 上传失败 (403)

**常见原因与解决方案**:

| 原因 | 错误信息 | 解决方案 |
|------|---------|---------|
| ACL 不允许 | `AccessDenied` | 修改 Bucket ACL |
| RAM 权限不足 | `AccessDenied` | 添加 RAM 授权策略 |
| STS 过期 | `SecurityTokenExpired` | 刷新 STS Token |
| 签名错误 | `SignatureDoesNotMatch` | 检查 AK/SK |
| 防盗链 | `AccessDenied` | 添加 Referer 白名单 |

### 4.2 CORS 跨域问题

**现象**: 浏览器报 `CORS policy` 错误

**解决方案**:
```bash
# 添加 CORS 规则
aliyun oss cors --method put oss://<bucket_name> --cors-configuration '{
  "CORSRule": [
    {
      "AllowedOrigin": ["https://example.com"],
      "AllowedMethod": ["GET", "PUT", "POST"],
      "AllowedHeader": ["*"],
      "ExposeHeader": ["ETag", "x-oss-request-id"],
      "MaxAgeSeconds": 3600
    }
  ]
}'
```

### 4.3 存储成本优化

**解决方案**:

| 方案 | 操作 | 节省 |
|------|------|------|
| 低频存储 | 30 天以上不频繁访问 | ~50% |
| 归档存储 | 90 天以上冷数据 | ~80% |
| 生命周期 | 自动转换/过期删除 | 自动化 |
| 删除碎片 | 清理未完成分片 | 空间回收 |

---

## 5. 权限边界

### 5.1 安全的只读操作
```bash
oss ls, oss stat
bucket-policy --method get
cors --method get
```

### 5.2 需要确认的操作
```bash
oss cp (上传/下载)
bucket-acl --method put
cors --method put
```

### 5.3 危险操作禁止执行
```bash
oss rm -r oss://bucket (递归删除)
oss bucket-delete (删除 Bucket)
修改 Bucket Policy 为完全公开
```

---

## 6. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-08
- 维护者: AIOps Team
