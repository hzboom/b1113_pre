#!/usr/bin/env python3
"""
测试配置读取
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from generate_repo_description import RepoDescriptionGenerator
    print("导入成功")
    
    # 测试配置读取
    generator = RepoDescriptionGenerator()
    print(f"Base URL: {generator.base_url}")
    print(f"Model: {generator.model_name}")
    print("配置读取成功")
    
    # 测试提示词读取
    prompt = generator.read_prompt_template()
    print(f"提示词长度: {len(prompt)} 字符")
    
    # 测试代码库分析
    analysis = generator.analyze_codebase()
    print(f"分析完成，找到 {len(analysis['source_files'])} 个源代码文件")
    print(f"文件列表: {analysis['source_files']}")
    
    print("所有测试通过！")
    
except Exception as e:
    print(f"测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)