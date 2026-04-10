# DCU 售后故障诊断平台 v1.0

基于 Python Flask + SQLite3 的智能故障诊断系统，内置 HYGON DCU 知识库，支持 AI 大模型联动分析。

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. （可选）配置 AI 分析 API Key
export ANTHROPIC_API_KEY=sk-ant-xxxxx

# 3. 启动服务
python app.py

# 4. 浏览器访问
http://127.0.0.1:5000
```

## 功能说明

### 📋 日志上传 & 分析
- 支持拖拽或点击上传 `.log` `.txt` `.dmesg` `.json` 格式
- 支持直接粘贴日志文本
- 优先匹配本地知识库（相关度 ≥ 12%）
- 知识库匹配不足时自动调用 AI 大模型分析

### 📚 知识库管理
- 手动新增条目（支持 6 大分类）
- JSON 批量导入（提供模板下载）
- 删除条目

### 🔍 知识库搜索
- 关键词搜索 + 分类筛选
- 相关度排序展示
- 点击查看详情

### 🕐 分析历史
- 记录最近 50 条分析日志
- 区分知识库匹配 / AI 分析

## 知识库分类

| 分类 | 说明 |
|------|------|
| 硬件驱动 | XID/SXID 错误码、驱动问题 |
| DTK | ROCm/HIP 环境、编译问题 |
| DAS | 存储设备故障 |
| 服务器 | DCU 直通、BIOS 配置 |
| 大模型 | vLLM、NCCL、分布式训练 |
| 通用模型 | 精度、量化、推理问题 |

## 内置知识库

已预置 25+ 条知识库条目，来源：
- HYGON DCU XID/SXID 错误手册 Rev 2.2.0
- DCU 直通问题总结
- DCU FAQ 汇总

## 批量导入 JSON 格式

```json
[
  {
    "category": "硬件驱动",
    "title": "XID XX 错误描述",
    "problem": "详细故障现象描述",
    "solution": "1. 步骤一\n2. 步骤二",
    "keywords": "关键词 空格分隔",
    "source": "来源文档"
  }
]
```

## 环境要求

- Python 3.9+
- 无 GPU 依赖，纯 CPU 运行
- AI 分析功能需要 ANTHROPIC_API_KEY 和网络访问
