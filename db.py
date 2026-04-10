import os
import re
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fault_diagnosis.db')
CATEGORIES = ['硬件驱动', 'DTK', 'DAS', '服务器', '大模型', '通用模型']
KB_THRESHOLD = 0.12   # Jaccard similarity threshold; below → call AI


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _tokenize(text):
    zh = re.findall(r'[\u4e00-\u9fff]', text)
    en = re.findall(r'[A-Za-z0-9_]+', text)
    return zh + [w.lower() for w in en]


def _jaccard(a_tokens, b_tokens):
    a, b = set(a_tokens), set(b_tokens)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def search_kb(query, category=None, top_k=5):
    conn = get_db()
    c = conn.cursor()
    if category and category != 'all':
        c.execute('SELECT * FROM knowledge_base WHERE category=?', (category,))
    else:
        c.execute('SELECT * FROM knowledge_base')
    rows = c.fetchall()
    conn.close()

    q_tokens = _tokenize(query)
    scored = []
    for row in rows:
        text = f"{row['title']} {row['problem']} {row['keywords']}"
        score = _jaccard(q_tokens, _tokenize(text))
        scored.append({'row': dict(row), 'score': round(score, 4)})

    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored[:top_k]


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category  TEXT NOT NULL,
            title     TEXT NOT NULL,
            problem   TEXT NOT NULL,
            solution  TEXT NOT NULL,
            keywords  TEXT DEFAULT '',
            source    TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS fault_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            filename   TEXT    DEFAULT '手动输入',
            content    TEXT    NOT NULL,
            result     TEXT,
            match_type TEXT,
            kb_ids     TEXT    DEFAULT '',
            score      REAL    DEFAULT 0,
            created_at TEXT    DEFAULT (datetime('now','localtime'))
        );
    ''')
    conn.commit()
    c.execute('SELECT COUNT(*) as n FROM knowledge_base')
    if c.fetchone()['n'] == 0:
        _seed_kb(c)
        conn.commit()
    conn.close()


def _seed_kb(c):
    entries = [
        ('硬件驱动','XID 2 · UMC UE 不可纠正错误',
         'DCU内核日志出现 XID:2 UMC UE 报错，HBM显存故障，任务异常退出',
         '1. 立即停止任务，收集 dmesg/hy-smi 日志\n2. 运行 HyFieldDiag 诊断工具\n3. 若重复复现，走 UMC repair → DCU Recovery 流程\n4. 修复失败联系硬件供应商走 RMA 流程',
         'XID 2 UMC UE HBM 显存 不可纠正 RAS 错误','HYGON XID/SXID 手册'),

        ('硬件驱动','XID 4 · GFX UE 不可纠正错误',
         'DCU内核日志出现 XID:4 GFX UE，图形计算单元发生不可纠正错误',
         '1. DCU 驱动自动执行 CU harvest → DCU Recovery\n2. 若恢复失败运行 HyFieldDiag\n3. 持续复现联系供应商',
         'XID 4 GFX UE CU harvest 不可纠正 RAS','HYGON XID/SXID 手册'),

        ('硬件驱动','XID 6/8/10/12/14/16/18/30 · RAS UE 系列',
         '日志出现 XID 6(SDMA) / 8(MMHUB) / 10(ATHUB) / 12(NBIO) / 14(HDP) / 16(HSL) / 18(DF) / 30(MCA) 不可纠正错误',
         '1. 放弃当前作业，重启节点\n2. 重启后仍复现 → 运行 HyFieldDiag\n3. 确认硬件故障 → 联系供应商报修（可能更换 DCU 卡或 UBB 底板）',
         'XID 6 8 10 12 14 16 18 30 SDMA MMHUB ATHUB NBIO HDP HSL DF MCA UE 不可纠正','HYGON XID/SXID 手册'),

        ('硬件驱动','XID 50 · DCU 高温警告',
         '日志报 XID:50 High temperature，DCU 温度超出阈值',
         '1. 检查机柜风扇/散热器状态\n2. 检查环境温度\n3. 降低任务负载或拆分任务\n4. 若温控硬件故障联系供应商',
         'XID 50 high temperature 高温 散热 过热','HYGON XID/SXID 手册'),

        ('硬件驱动','XID 51 · DCU isolation（掉卡/故障隔离）',
         'XID:51 出现，DCU 被系统隔离，hy-smi 看不到卡',
         '1. 执行 AC/DC 重启尝试恢复\n2. 恢复后做 XID 复现测试\n3. 仍复现 → 硬件检查或报修',
         'XID 51 isolation 掉卡 隔离 critical error','HYGON XID/SXID 手册'),

        ('硬件驱动','XID 76 · QCM fence timeout',
         '日志出现 XID:76，DCU QCM 命令超时，任务卡死',
         '1. 重启节点\n2. 重启后压测 DCU\n3. 压测失败联系供应商\n4. 可能源于软件逻辑或硬件故障',
         'XID 76 QCM fence timeout 超时 fatal','HYGON XID/SXID 手册'),

        ('硬件驱动','XID 77 · HDP timeout',
         '日志出现 XID:77 HDP timeout，Host Data Path 超时',
         '1. 重启节点，观察是否复现\n2. 复现后联系供应商并提供完整 dmesg',
         'XID 77 HDP timeout 超时','HYGON XID/SXID 手册'),

        ('硬件驱动','XID 81 · VM fault（显存页错误）',
         'XID:81 VM fault，DCU 虚拟内存访问违规，任务崩溃',
         '1. 检查应用代码是否有越界显存访问\n2. 升级驱动至最新版本\n3. 若硬件相关 → 运行 HyFieldDiag',
         'XID 81 VM fault 显存 内存 越界 page fault','HYGON XID/SXID 手册'),

        ('硬件驱动','XID 82 · ATHUB error（PCIe 上行错误）',
         'XID:82 ATHUB ERR，PCIe 上行传输出现错误',
         '1. 检查 PCIe 物理连接和金手指\n2. 重启节点\n3. 仍复现 → 联系供应商检查主板/槽位',
         'XID 82 ATHUB PCIe 上行 传输 错误','HYGON XID/SXID 手册'),

        ('硬件驱动','XID 87 · 驱动固件加载失败',
         'XID:87 Driver firmware error，驱动或固件无法加载',
         '1. 检查驱动版本是否与固件匹配\n2. 重新安装驱动（hydcu-dkms）\n3. 若 VBIOS 损坏使用 hyflash 重刷\n4. 手动 modprobe hydcu 验证',
         'XID 87 driver firmware 固件 驱动加载 init error','HYGON XID/SXID 手册'),

        ('硬件驱动','XID 160 · PCIe link lost（链路丢失）',
         'XID:160 PCIE link lost，DCU 与主机 PCIe 链路中断',
         '1. 检查 PCIe 信号线和 risder 卡连接\n2. 执行 AC/DC 重启\n3. 用 lspci 确认设备枚举\n4. 硬件故障联系供应商',
         'XID 160 PCIE link lost 链路 断链 掉卡 critical','HYGON XID/SXID 手册'),

        ('硬件驱动','XID 120/130 · ECC 高错误率预警',
         'XID:120（HBM 行重映射事件）或 XID:130（单比特 ECC 错误率过高），属于预警级别',
         '1. 纳入日常监控，暂不影响运行\n2. XID 120 触发 Row Remapping/Page Retirement 机制\n3. 若频率上升或伴随 UE 错误 → 运行 HyFieldDiag\n4. 提前安排硬件维护窗口',
         'XID 120 130 ECC row remapping page retirement 单比特 预警 non-fatal','HYGON XID/SXID 手册'),

        ('硬件驱动','XID 190/200/201/300 · DCU 初始化失败',
         'XID:190/200/201/300，驱动初始化、VBIOS 启动或 SMU 固件加载失败',
         '1. 检查驱动和固件版本匹配性\n2. 使用 hyflash --allInfo 验证 VBIOS 状态\n3. 重刷 VBIOS：./hyflash --index a --update <vbios.bin>\n4. 手动 modprobe hydcu\n5. 无法恢复 → 联系供应商',
         'XID 190 200 201 300 初始化 VBIOS SMU 固件 驱动加载失败 init','HYGON XID/SXID 手册'),

        ('服务器','虚拟机 DCU 显示 rev ff 状态（卡FF问题）',
         '虚拟机安装驱动后 lspci 看到 DCU 状态为 rev ff，如 "KONGMING (rev ff)"',
         '方案1（推荐）：升级驱动到 6.2.26 或更高版本\n方案2：刷新 VBIOS 至已验证版本（5.711.001200o / 5.714.001200p / 5.715.001200r）\n命令：./hyflash --index a --update <vbios.bin>，刷新后重启物理机',
         '虚拟机 rev ff 卡FF baco reset 中断 vbios 直通 passthrough','DCU直通问题总结'),

        ('服务器','pci=realloc 导致 DCU BAR 地址缺失',
         '虚拟机安装驱动报 "Adapter BAR init failed, smn access failed!", Region 5 显示 <ignored>',
         '1. 编辑 /etc/default/grub，删除内核参数 pci=realloc\n2. 重新生成引导配置：grub2-mkconfig -o /boot/efi/EFI/*/grub.cfg\n3. 重启服务器生效',
         'pci realloc BAR bar init failed smn access Region ignored grub 直通','DCU直通问题总结'),

        ('服务器','DCU BAR 地址超出 44bit',
         '驱动安装正常但 PyTorch 无法调用 DCU，lspci 看到 Region 0 BAR 地址超出 44bit',
         '检查虚拟机 XML 配置文件中的 maxMemory 设置，将其调小到 16T 以下，或直接删除该配置项：<maxMemory slots=\'16\' unit=\'KiB\'>...</maxMemory>',
         'BAR 44bit maxMemory xml 直通 pytorch 无法调用','DCU直通问题总结'),

        ('服务器','vfio 与 hydcu_pci_fixup_header 加载顺序错误',
         '虚拟机报 "Unknown PCI header type \'127\'", lsmod 看到两个模块都存在',
         '方案1：修改 /etc/rc.local 添加重新加载顺序：\nrmmod vfio-pci → rmmod hydcu_pci_fixup_header → modprobe hydcu_pci_fixup_header → modprobe vfio-pci\n方案2：删除 /etc/modprobe.d/ 或 /etc/modules-load.d/ 下的 vfio.conf',
         'vfio pci fixup header 127 加载顺序 直通 虚拟机','DCU直通问题总结'),

        ('服务器','iommu group 组导致 DCU 无法挂载',
         '挂载时报 "group x is not viable, Please ensure all devices within the iommu_group are bound to their vfio bus driver"',
         '1. 确认 iommu group 内的所有设备都绑定到 vfio-pci\n2. BIOS 开启 ACS：路径 Chipset → NBIO Common Options → ACS Control → enable\n3. 内核参数加 pcie_acs_override=downstream（ACS 关闭时无效）',
         'iommu group vfio viable ACS BIOS 直通 挂载','DCU直通问题总结'),

        ('服务器','虚拟机 DCU 掉卡（hy-smi 少卡）',
         '虚拟机 lspci 卡数正常，hy-smi 少卡；dmesg 报 "Fatal error during GPU init"',
         '方案1（在线修复，无需重启 VBIOS）：\n  1. lspci 确认掉卡位置 i\n  2. hy-smi --unloaddriver\n  3. ./dcuAidTool -br -dcu i\n  4. hy-smi --loaddriver\n方案2：更新驱动到 6.2.30 并在安装时选择更新 VBIOS，重启物理机',
         '虚拟机 掉卡 hy-smi 少卡 baco reset gddr fatal dcuAidTool','DCU直通问题总结'),

        ('服务器','Ubuntu OS 无法实现 DCU 直通',
         'Ubuntu 系统下虚拟机挂载 DCU 失败，vfio 无法卸载',
         'Ubuntu 的 vfio 控制编译进内核（CONFIG_VFIO_PCI=y），无法手动 rmmod。\n解决：编译支持模块化 vfio-pci 的自定义内核，或改用 CentOS/RHEL 系发行版进行直通操作',
         'ubuntu vfio CONFIG_VFIO_PCI 直通 模块 内核','DCU直通问题总结'),

        ('服务器','虚拟机 DCU P2P 带宽偏低',
         '虚拟机卡间双向带宽仅 25-38 GB/s，物理机正常 54-56 GB/s',
         '这是 DCU 直通架构限制：虚拟机显存地址必须通过 IOMMU 重映射，无法实现真正的 P2P 直连。\n无法完全规避；如性能敏感，建议使用物理机部署或评估 MIG/虚拟化替代方案',
         'P2P 带宽 IOMMU 虚拟机 直通 性能','DCU直通问题总结'),

        ('硬件驱动','SXID 200/201 · HySwitch 驱动加载/寄存器超时',
         'HySwitch 驱动加载失败（SXID:200）或读寄存器超时（SXID:201），节点资源无法使用',
         '1. 检查 HySwitch 驱动和固件版本匹配\n2. 重启节点确认是否复现\n3. 复现后运行故障侦测套件\n4. 无法恢复报技服人员处理',
         'SXID 200 201 HySwitch 驱动 加载 寄存器 超时','HYGON XID/SXID 手册'),

        ('硬件驱动','SXID 204 · HSL Link UE（不可恢复传输错误）',
         'SXID:204 HySwitch HSL Link Chain UE，DCU 互联通路出现不可恢复错误，运行中作业不可信',
         '1. 立即放弃当前作业\n2. 重启节点观察是否复现\n3. 重新部署驱动和固件\n4. 仍不可恢复 → 运行故障侦测套件，故障卡报技服',
         'SXID 204 HSL Link UE 不可恢复 互联 HySwitch','HYGON XID/SXID 手册'),

        ('硬件驱动','SXID 207 · HySwitch PCIe Link Lost',
         'SXID:207，HySwitch 芯片与 CPU PCIe 断链，需节点 DC 修复',
         '1. 重启节点确认是否恢复\n2. 通过带外管理升级固件\n3. 无法恢复报技服人员处理',
         'SXID 207 HySwitch PCIe link lost 断链','HYGON XID/SXID 手册'),

        ('硬件驱动','SXID 251/253/255/257 · HFM 任务错误（HySwitch 建链失败）',
         'SXID:251/253/255/257 等，HFM 任务执行错误导致 DCU 驱动无法加载，全量 DCU 不可用',
         '1. 重启节点\n2. 检查 HySwitch 驱动和固件版本\n3. 通过带外管理升级固件尝试恢复\n4. 无法恢复报技服人员处理',
         'SXID 251 253 255 257 HFM HySwitch 建链 DCU 驱动 加载失败','HYGON XID/SXID 手册'),

        ('DTK','DTK/ROCm 环境变量配置错误',
         'import torch 后找不到 DCU，torch.dcu.is_available() 返回 False',
         '1. 确认 DTK 版本与驱动版本匹配\n2. 设置环境变量：export HIP_VISIBLE_DEVICES=0,1,...\n3. source /opt/dtk/env.sh\n4. 使用 hy-smi 确认 DCU 已被驱动识别',
         'DTK ROCm pytorch torch dcu available 环境变量 import','DTK常见问题'),

        ('DTK','HIP kernel 编译失败',
         'hipcc 编译报错，或运行时 kernel launch failed',
         '1. 检查 DTK 版本（dtk --version）\n2. 检查 GPU 架构参数 --amdgpu-target=gfx906/gfx928\n3. 确认 LLVM/CLANG 版本兼容\n4. 查看 /var/log/dtk/ 详细日志',
         'HIP hipcc kernel 编译 launch failed gfx906 gfx928 DTK','DTK常见问题'),

        ('大模型','vLLM 推理显存 OOM',
         'vLLM 启动时或推理过程中报 OOM（Out of Memory），显存不足',
         '1. 减小 --gpu-memory-utilization（默认 0.9，可调至 0.8）\n2. 减小 --max-model-len 限制上下文长度\n3. 启用 --quantization awq/gptq 量化推理\n4. 使用多卡 tensor parallel：--tensor-parallel-size N',
         'vLLM OOM out of memory 显存 推理 量化 tensor parallel','大模型部署'),

        ('大模型','多卡训练 NCCL 通信超时/挂起',
         '分布式训练时 NCCL 报 timeout 或进程卡住无响应',
         '1. 检查网络互联（IB/RoCE）配置：hy-smi --showbus 确认 HSL 拓扑\n2. export NCCL_DEBUG=INFO 收集日志\n3. 检查防火墙/SELinux 是否阻断通信端口\n4. 降低 NCCL_TIMEOUT 并增加 retry 次数',
         'NCCL 超时 挂起 分布式 多卡 训练 通信 IB RoCE','大模型训练'),

        ('DAS','DAS 存储挂载失败',
         'DAS 存储设备无法挂载，报 I/O error 或 device not found',
         '1. 检查物理连接（SAS/NVMe cable）\n2. lsblk / nvme list 确认设备识别\n3. 检查 udev 规则和 multipath 配置\n4. 使用 smartctl -a /dev/sdX 检查磁盘健康',
         'DAS 存储 挂载 IO error device not found SAS NVMe','DAS存储问题'),

        ('通用模型','模型推理精度异常',
         '模型输出结果异常，与预期精度差异大',
         '1. 确认数据预处理与训练时保持一致\n2. 检查量化配置（fp16/bf16/int8）是否匹配\n3. 验证模型权重文件完整性（md5/sha256）\n4. 用小批量 CPU 推理对比结果',
         '精度 异常 量化 fp16 bf16 int8 模型 权重','通用模型部署'),
    ]
    sql = 'INSERT INTO knowledge_base(category,title,problem,solution,keywords,source) VALUES(?,?,?,?,?,?)'
    c.executemany(sql, entries)
