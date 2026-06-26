# 工具系统详细说明

## 设计理念

DevAgent 的工具层遵循 **统一接口 + 安全沙箱** 原则：

1. **统一返回格式**：所有工具返回 `ToolResult(success, data, error)`
2. **操作日志**：所有工具调用自动记录
3. **安全边界**：文件操作限制在工作目录内，Shell 命令有黑白名单
4. **可替换**：未来可无缝切换到 MCP 协议

## 工具分类

### 文件工具 (FileTool)

```python
tools.file.read("src/main.py")       # → 读取文件内容
tools.file.write("src/main.py", ...)  # → 写入文件（自动创建父目录）
tools.file.list_dir("src/")          # → 列出目录
tools.file.exists("src/main.py")      # → 检查是否存在
tools.file.snapshot(".")             # → 获取项目文件树
tools.file.delete("tmp.txt")         # → 删除文件
```

**安全措施**：
- 所有路径自动解析到 workspace 内，防止 `../../etc/passwd` 目录穿越
- 操作失败返回 `ToolResult(success=False, error=...)`，不抛异常

### Shell 工具 (ShellTool)

```python
tools.shell.run("pytest tests/")     # → 执行命令
tools.shell.run("git diff")          # → Git diff
tools.shell.run_python("print(1+1)") # → 执行 Python 片段
```

**安全措施**：
- 危险命令黑名单：`rm -rf /`、`dd`、`mkfs`、fork bomb
- 命令超时（默认 60 秒）
- 输出截断（最多 10000 字符）
- `run_python()` 用临时文件 + 自动清理

### Git 工具 (GitTool)

```python
tools.git.status()              # → git status
tools.git.diff()                # → git diff
tools.git.log(10)               # → 最近 10 条提交
tools.git.branch()              # → 当前分支
tools.git.add("src/")           # → git add
tools.git.commit("feat: ...")   # → git commit
tools.git.create_branch("dev")  # → 创建分支
```

## 工具注册表 (ToolRegistry)

所有 worker 通过 `ToolRegistry` 访问工具，而不是直接调用底层实现：

```python
class ToolRegistry:
    def __init__(self, workspace: Path):
        self.file = FileTool(workspace)
        self.shell = ShellTool(workspace)
        self.git = GitTool(workspace)

        # 🆕 代码助手工具
        self.search = CodeSearchTool(workspace)
        self.project = ProjectTool(workspace)
        self.ast = ASTTool(workspace)
        self.diff = DiffTool(workspace)
        self.diagnose = DiagnoseTool(workspace)
```

**向 LLM 暴露工具描述**：

```python
registry.get_tools_description()
# 输出 Markdown 格式的工具列表，嵌入 LLM 的 system prompt
```

---

## 🆕 代码助手专用工具

以下是代码助手场景（代码理解、重构、诊断）所需的额外工具。

### 代码搜索工具 (CodeSearchTool)

代码助手最核心的能力——在已有代码库中精准找到想要的代码。

```python
# 全文搜索（基于正则或文本匹配）
tools.search.grep("def create_user")            # → 所有包含 create_user 的行
tools.search.grep(r"TODO|FIXME|HACK")           # → 找到所有技术债标记
tools.search.grep("import.*pandas", "*.py")     # → 所有导入 pandas 的文件

# 语义搜索（基于向量）
tools.search.semantic("用户登录认证逻辑")         # → 语义匹配最相关的代码段
tools.search.semantic("database connection pool", limit=5)

# 查找引用
tools.search.find_usages("UserModel")            # → 所有引用 UserModel 的地方
tools.search.find_usages("def calculate_price")  # → 所有调用点

# 查找定义
tools.search.find_definition("UserModel")        # → 跳转到定义位置
tools.search.find_definition("calculate_price")
```

**安全措施**：
- 只能搜索 workspace 内的代码
- 语义搜索用的 embedding 在本地计算（不泄露代码到外部API）

### 项目感知工具 (ProjectTool)

让 Agent 理解项目整体结构，而非孤立地看单个文件。

```python
tools.project.structure()                # → 项目目录树（仅代码文件）
tools.project.language_stats()           # → 语言分布（70% Python, 20% JS, 10% SQL）
tools.project.dependency_graph()         # → 模块依赖关系图
tools.project.top_level_modules()        # → 顶层包/模块列表
tools.project.entry_points()             # → main() / app 等入口点
tools.project.config_files()             # → pyproject.toml, .env, Dockerfile 等
```

**使用时机**：
- Agent 启动时自动调用 `project.structure()` 建立初始认知
- 诊断/重构/问答前，调用 `dependency_graph()` 了解模块关系
- 代码生成前，调用 `config_files()` 了解项目配置

### AST 分析工具 (ASTTool) 🆕

比文本搜索更精准，直接解析代码的抽象语法树。

```python
tools.ast.parse("src/models/user.py")            # → 返回 AST 结构
tools.ast.list_functions("src/services/")         # → 所有函数签名
tools.ast.list_classes("src/models/")             # → 所有类及方法
tools.ast.list_imports("src/services/order.py")   # → 该文件的所有 import
tools.ast.complexity("src/utils/helpers.py")      # → 圈复杂度分析
tools.ast.call_graph("src/services/order.py")     # → 函数调用关系图
```

**为什么需要 AST 工具**：
- 文本搜索 `def create` 会误匹配注释中的 `# def create...`
- AST 分析 `list_functions()` 只返回真正的函数定义
- 重构时需要知道"谁调用了这个函数"（call graph）
- 复杂度分析能发现需要重构的"坏味道"函数

### 代码对比工具 (DiffTool) 🆕

```python
tools.diff.compare_files("v1/user.py", "v2/user.py")    # → 两个文件逐行对比
tools.diff.git_diff("HEAD~3..HEAD")                       # → Git diff
tools.diff.semantic_diff("v1/", "v2/")                    # → 语义级差异
```

### 诊断工具 (DiagnoseTool) 🆕

Bug 诊断专用。

```python
tools.diagnose.trace_error(traceback_text)     # → 解析堆栈，映射到文件和行
tools.diagnose.check_null_paths(file)          # → 检测可能的 None 路径
tools.diagnose.check_race_conditions(file)     # → 检测并发竞争条件
tools.diagnose.check_resource_leaks(file)      # → 检测未关闭的文件/连接
```

---

## 工具使用场景对照表

| 场景 | 需要哪些工具 |
|------|------------|
| **代码生成** | FileTool(写) + ShellTool(运行测试) |
| **代码解释** | FileTool(读) + ASTTool + ProjectTool |
| **重构分析** | FileTool(读) + ASTTool + DiffTool + CodeSearchTool |
| **Bug诊断** | FileTool(读) + DiagnoseTool + ASTTool(call_graph) + CodeSearchTool |
| **代码审查** | FileTool(读) + ASTTool(complexity) + DiffTool |
| **技术问答** | FileTool(读) + ProjectTool + CodeSearchTool(semantic) |
| **项目扫描** | ProjectTool(all) + ASTTool(list_functions/list_classes) |

---

## 未来扩展：MCP 协议

当需要更正规的工具接入时，可以把 `ToolRegistry` 替换为 MCP Server：

```
当前: Worker → ToolRegistry → 各种工具
未来: Worker → MCP Client → MCP Server → 各种工具
```

迁移成本低，因为接口设计一致。

## 添加自定义工具

```python
# 1. 创建工具类
class DatabaseTool:
    def __init__(self, db_url: str):
        self.db_url = db_url

    def query(self, sql: str) -> ToolResult:
        try:
            # ... 执行 SQL
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

# 2. 注册到 ToolRegistry
class ToolRegistry:
    def __init__(self, workspace: Path):
        self.file = FileTool(workspace)
        self.shell = ShellTool(workspace)
        self.git = GitTool(workspace)
        self.db = DatabaseTool("sqlite:///project.db")  # 新增

# 3. 更新工具描述
def get_tools_description(self) -> str:
    return """
    ...
    ### 数据库操作 (db)
    - db.query(sql) → 执行 SQL 查询
    """
```
