#!/usr/bin/env python3
"""
生成代码库简介的脚本
调用Claude Opus 4-5模型，根据代码库内容生成project_repo.md
"""

import os
import json
import requests
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

class RepoDescriptionGenerator:
    def __init__(self, config_path: str = "../config.json"):
        """
        初始化生成器，加载配置
        
        Args:
            config_path: config.json文件路径
        """
        self.config = self._load_config(config_path)
        self.base_url = self.config.get("BASE_URL")
        self.api_key = self.config.get("TOKEN")
        self.model_name = self.config.get("MODEL_NAME_CLAUDE_OPUS")
        
        if not all([self.base_url, self.api_key, self.model_name]):
            raise ValueError("配置文件中缺少必要的API配置")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"配置文件 {config_path} 不存在")
            raise
        except json.JSONDecodeError:
            print(f"配置文件 {config_path} JSON格式错误")
            raise
    
    def read_prompt_template(self, prompt_path: str = "../prompt/repo_prompt.md") -> str:
        """读取提示词模板"""
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            print(f"提示词文件 {prompt_path} 不存在")
            raise
    
    def analyze_codebase(self, root_dir: str = "..") -> Dict[str, Any]:
        """
        分析代码库内容，提取关键信息
        
        Returns:
            包含代码库信息的字典
        """
        analysis = {
            "project_name": "",
            "description": "",
            "technologies": [],
            "key_files": [],
            "readme_content": "",
            "source_files": []
        }
        
        root_path = Path(root_dir)
        
        # 读取README.md
        readme_path = root_path / "README.md"
        if readme_path.exists():
            with open(readme_path, 'r', encoding='utf-8') as f:
                analysis["readme_content"] = f.read()
        
        # 收集源代码文件
        src_dir = root_path / "src"
        if src_dir.exists():
            for file in src_dir.glob("*.java"):
                analysis["source_files"].append(file.name)
        
        # 收集其他关键文件
        for file in root_path.glob("*"):
            if file.is_file() and file.suffix in [".java", ".py", ".md", ".json", ".yml", ".yaml"]:
                analysis["key_files"].append(file.name)
        
        return analysis
    
    def generate_prompt(self, analysis: Dict[str, Any], template: str) -> str:
        """
        根据分析结果和模板生成最终提示词
        
        Args:
            analysis: 代码库分析结果
            template: 提示词模板
            
        Returns:
            完整的提示词
        """
        # 从README中提取项目名称
        readme_lines = analysis["readme_content"].split('\n')
        project_name = "Java Snake Game"
        for line in readme_lines:
            if line.startswith("# "):
                project_name = line.strip("# ").strip()
                break
        
        # 构建代码库内容摘要
        codebase_summary = f"""
项目名称: {project_name}

README内容摘要:
{analysis['readme_content'][:1000]}...

源代码文件:
{', '.join(analysis['source_files'])}

关键文件:
{', '.join(analysis['key_files'])}
"""
        
        # 将代码库摘要插入到模板中
        prompt = template + f"""

请基于以下代码库内容生成简介：

{codebase_summary}

请严格按照以下要求生成：
1. 字数在100-300字之间
2. 必须包含目标、要解决的问题、所用技术栈等信息
3. 语言简洁专业
4. 直接输出简介内容，不要添加额外说明
"""
        
        return prompt
    
    def call_claude_api(self, prompt: str) -> str:
        """
        调用Claude API生成简介
        
        Args:
            prompt: 完整的提示词
            
        Returns:
            API返回的简介内容
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
            
        except requests.exceptions.RequestException as e:
            print(f"API调用失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"响应状态码: {e.response.status_code}")
                print(f"响应内容: {e.response.text}")
            raise
    
    def write_description_to_file(self, description: str, output_path: str = "../project_repo.md"):
        """将生成的简介写入文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(description)
        print(f"简介已写入文件: {output_path}")
    
    def setup_git_and_push(self, github_user: str, github_password: str, repo_name: Optional[str] = None):
        """
        配置Git并将项目推送到GitHub，如果仓库不存在则创建
        
        Args:
            github_user: GitHub用户名
            github_password: GitHub密码或个人访问令牌
            repo_name: 仓库名称（默认为当前目录名）
        """
        print("配置Git并推送到GitHub...")
        
        # 确定仓库名称
        if repo_name is None:
            repo_name = Path("..").resolve().name
        
        repo_url_https = f"https://github.com/{github_user}/{repo_name}.git"
        repo_url_ssh = f"git@github.com:{github_user}/{repo_name}.git"
        api_url = f"https://api.github.com/repos/{github_user}/{repo_name}"
        
        # 尝试使用GitHub API检查仓库（使用基本认证）
        auth = (github_user, github_password)
        headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        
        api_success = False
        try:
            print(f"检查仓库 {github_user}/{repo_name} 是否存在...")
            response = requests.get(api_url, headers=headers, auth=auth, timeout=10)
            
            if response.status_code == 404:
                print("仓库不存在，正在创建...")
                # 创建仓库
                create_data = {
                    "name": repo_name,
                    "description": "Java Snake Game project",
                    "private": False,
                    "auto_init": False
                }
                create_response = requests.post(
                    f"https://api.github.com/user/repos",
                    headers=headers,
                    auth=auth,
                    json=create_data,
                    timeout=10
                )
                if create_response.status_code in (201, 200):
                    print(f"仓库 {repo_name} 创建成功")
                else:
                    print(f"仓库创建失败: {create_response.status_code} - {create_response.text}")
                    # 继续尝试推送，可能仓库已存在但权限不足
            elif response.status_code == 200:
                print("仓库已存在")
            else:
                print(f"检查仓库时出错: {response.status_code} - {response.text}")
                # 继续尝试推送
            api_success = True
        except Exception as e:
            print(f"GitHub API调用失败，将跳过仓库检查: {e}")
        
        # 初始化本地Git仓库（如果尚未初始化）
        if not os.path.exists("../.git"):
            print("初始化Git仓库...")
            subprocess.run(["git", "init"], cwd="..", check=True)
        
        # 配置远程仓库
        print("配置远程仓库...")
        # 移除可能已存在的远程仓库
        subprocess.run(["git", "remote", "remove", "origin"], cwd="..", capture_output=True)
        
        # 尝试使用HTTPS with password/token进行推送
        if api_success:
            try:
                auth_repo_url = f"https://{github_user}:{github_password}@github.com/{github_user}/{repo_name}.git"
                subprocess.run(["git", "remote", "add", "origin", auth_repo_url], cwd="..", check=True)
                print("使用HTTPS基本认证配置远程仓库")
            except Exception as e:
                print(f"HTTPS基本认证失败，尝试使用SSH: {e}")
                subprocess.run(["git", "remote", "remove", "origin"], cwd="..", capture_output=True)
                subprocess.run(["git", "remote", "add", "origin", repo_url_ssh], cwd="..", check=True)
                print("使用SSH配置远程仓库")
        else:
            # 直接使用SSH
            subprocess.run(["git", "remote", "add", "origin", repo_url_ssh], cwd="..", check=True)
            print("使用SSH配置远程仓库")
        
        # 添加所有文件并提交
        print("添加文件并提交...")
        subprocess.run(["git", "add", "."], cwd="..", check=True)
        # 检查是否有更改需要提交
        result = subprocess.run(["git", "status", "--porcelain"], cwd="..", capture_output=True, text=True)
        if result.stdout.strip():
            subprocess.run(["git", "commit", "-m", "Add project description generated by script"], 
                          cwd="..", check=True)
        else:
            print("没有更改需要提交")
        
        # 重命名分支为main（如果当前不是main）
        print("确保分支为main...")
        subprocess.run(["git", "branch", "-M", "main"], cwd="..", check=True)
        
        # 推送到GitHub
        print("推送到GitHub...")
        try:
            result = subprocess.run(["git", "push", "-u", "origin", "main"], cwd="..", capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                print(f"推送失败: {result.stderr}")
                # 尝试强制推送（如果历史不一致）
                print("尝试强制推送...")
                subprocess.run(["git", "push", "-f", "origin", "main"], cwd="..", check=True)
        except subprocess.TimeoutExpired:
            print("推送超时，可能网络问题")
            raise
        except Exception as e:
            print(f"推送失败: {e}")
            raise
        
        print(f"项目已成功推送到GitHub: {repo_url_https}")

def main():
    """主函数"""
    try:
        # 初始化生成器
        generator = RepoDescriptionGenerator()
        
        # 读取提示词模板
        prompt_template = generator.read_prompt_template()
        
        # 分析代码库
        print("正在分析代码库...")
        analysis = generator.analyze_codebase()
        
        # 生成提示词
        print("正在生成提示词...")
        prompt = generator.generate_prompt(analysis, prompt_template)
        
        # 调用Claude API生成简介
        print("正在调用Claude API生成简介...")
        description = generator.call_claude_api(prompt)
        
        # 写入文件
        generator.write_description_to_file(description)
        
        # 推送到GitHub
        github_user = "hzboom"
        github_password = "330127sw"
        generator.setup_git_and_push(github_user, github_password)
        
        print("脚本执行完成！")
        
    except Exception as e:
        print(f"脚本执行失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()