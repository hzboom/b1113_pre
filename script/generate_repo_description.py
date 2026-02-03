#!/usr/bin/env python3
"""
生成代码库简介的脚本
调用Claude Opus 4-5模型，根据代码库内容生成project_repo.md
"""

import os
import json
import requests
from pathlib import Path
from typing import Dict, Any

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
    
    def setup_git_and_push(self, repo_url: str, github_key: str):
        """
        配置Git并将项目推送到GitHub
        
        Args:
            repo_url: GitHub仓库URL
            github_key: GitHub Personal Access Token
        """
        print("配置Git并推送到GitHub...")
        
        # 这里实现Git操作
        # 注意：由于安全原因，实际部署时可能需要更复杂的处理
        # 这里提供基本实现框架
        
        # 检查是否已初始化Git仓库
        if not os.path.exists("../.git"):
            os.system("cd .. && git init")
        
        # 添加远程仓库
        os.system(f'cd .. && git remote add origin {repo_url.replace("https://", f"https://{github_key}@")}')
        
        # 添加所有文件并提交
        os.system('cd .. && git add .')
        os.system('cd .. && git commit -m "Add project description generated by script"')
        
        # 推送到GitHub
        os.system('cd .. && git branch -M main')
        os.system('cd .. && git push -u origin main')
        
        print("项目已成功推送到GitHub")

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
        github_url = "https://github.com/hzboom/b1113_pre"
        github_key = "DBEKUY6Nx2UnjLY1uIZbbv6o0w8pl3duVLoA01PtCUs"
        generator.setup_git_and_push(github_url, github_key)
        
        print("脚本执行完成！")
        
    except Exception as e:
        print(f"脚本执行失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()