#!/usr/bin/env python3
"""
测试GitHub仓库创建和推送功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from generate_repo_description import RepoDescriptionGenerator

def test_github():
    try:
        generator = RepoDescriptionGenerator()
        
        # 测试GitHub功能
        github_user = "hzboom"
        github_token = "DBEKUY6Nx2UnjLY1uIZbbv6o0w8pl3duVLoA01PtCUs"
        
        print("开始测试GitHub仓库创建和推送...")
        generator.setup_git_and_push(github_user, github_token)
        print("测试成功！")
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_github()