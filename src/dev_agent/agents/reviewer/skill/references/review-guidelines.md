# 代码审查规则与严重性分级标准

## 严重性定义

| 级别 | 图标 | 定义 | 处理时限 |
|------|------|------|---------|
| **严重** | 🔴 | 可能导致运行时错误、安全漏洞或数据丢失 | 立即修复 |
| **一般** | 🟡 | 代码质量问题，长期累积可能导致维护困难 | 下次重构 |
| **优化** | 🔵 | 改进建议，不影响功能 | 按计划处理 |

## 按编程语言的检查规则

### Python
- **严重**: eval(), exec(), 硬编码密码, 裸露的 except:
- **一般**: console.log → logging, import *, 类型注解缺失
- **优化**: f-string 效率, 列表推导式 vs 循环

### JavaScript/TypeScript
- **严重**: eval(), innerHTML, document.write, 未处理的 Promise rejection
- **一般**: console.log 残留, var 声明, == vs ===
- **优化**: 可选链 ?, 模板字面量, Array.reduce

### Go
- **严重**: panic 未恢复, 未检查 error
- **一般**: 导出函数无注释, 魔数
- **优化**: sync.Pool, 预分配 slice capacity

### Java
- **严重**: System.exit(), 资源未关闭 (try-with-resources)
- **一般**: 空 catch 块, System.out.println
- **优化**: 字符串拼接 → StringBuilder

## 通用检查项

### 安全检查（严重）
- 硬编码凭据（password, api_key, token, secret）
- SQL 注入风险（字符串拼接 SQL）
- XSS 风险（innerHTML, dangerouslySetInnerHTML）
- 路径遍历风险（未清洗的用户输入作为文件路径）

### 错误处理（严重/一般）
- 未处理的异常
- 裸露的 except/pass
- 未检查的错误返回值

### 代码质量（一般/优化）
- TODO/FIXME 标记
- 死代码 / 不可达代码
- 过长函数（>50行）
- 过深嵌套（>4层）
- 重复代码

### 性能（优化）
- 循环中的数据库查询
- 大文件的同步读取
- 不必要的对象创建
