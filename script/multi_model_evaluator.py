
#!/usr/bin/env python3
"""
多模型评估与代码合并脚本

该脚本读取配置文件，使用多个AI模型对项目进行处理，
然后使用DeepSeek模型对结果进行评分，选择最佳结果并合并到main分支。
"""

import json
import os
import sys
import logging
import subprocess
import tempfile
import shutil
import re
import time
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理器，负责读取和解析config.json"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = {}
        
    def load(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logger.info(f"配置文件加载成功: {self.config_path}")
            return self.config
        except FileNotFoundError:
            logger.error(f"配置文件不存在: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"配置文件JSON格式错误: {e}")
            raise
    
    def get_prompt(self) -> str:
        """获取PROMPT"""
        return self.config.get("PROMPT", "")
    
    def get_base_url(self) -> str:
        """获取API基础URL"""
        return self.config.get("BASE_URL", "")
    
    def get_token(self) -> str:
        """获取API令牌"""
        return self.config.get("TOKEN", "")
    
    def get_model_names(self) -> Dict[str, str]:
        """获取所有模型名称"""
        return {
            "deepseek": self.config.get("MODEL_NAME_DEEPSEEK", ""),
            "claude_opus": self.config.get("MODEL_NAME_CLAUDE_OPUS", ""),
            "dou_bao": self.config.get("MODEL_NAME_DOU_BAO", ""),
            "gpt": self.config.get("MODEL_NAME_GPT", "")
        }
    
    def get_github_config(self) -> Dict[str, str]:
        """获取GitHub配置"""
        return {
            "ssh_key": self.config.get("SSH_KEY", ""),
            "pat_token": self.config.get("PAT_TOKEN", "")
        }
    
    def get_retry_config(self) -> Dict[str, Any]:
        """获取重试配置"""
        return {
            "max_retries": self.config.get("MAX_RETRIES", 3),
            "retry_delay": self.config.get("RETRY_DELAY", 1.0),
            "retry_backoff_factor": self.config.get("RETRY_BACKOFF_FACTOR", 2.0)
        }


class ProjectProcessor:
    """项目处理器，负责管理项目状态和文件操作"""
    
    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()
        self.temp_dir = None
        
    def get_project_info(self) -> Dict[str, Any]:
        """获取项目信息（git状态、文件列表等）"""
        info = {
            "path": str(self.project_path),
            "is_git_repo": self._is_git_repo(),
            "current_branch": self._get_current_branch(),
            "files": self._list_source_files()
        }
        return info
    
    def _is_git_repo(self) -> bool:
        """检查是否为git仓库"""
        try:
            subprocess.run(
                ["git", "status"],
                cwd=self.project_path,
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _get_current_branch(self) -> str:
        """获取当前分支"""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "unknown"
    
    def _list_source_files(self) -> List[str]:
        """列出源代码文件"""
        source_files = []
        extensions = [".java", ".py", ".js", ".ts", ".cpp", ".c", ".go", ".rs", ".php"]
        for ext in extensions:
            for file in self.project_path.rglob(f"*{ext}"):
                if not any(part.startswith('.') for part in file.parts):
                    source_files.append(str(file.relative_to(self.project_path)))
        logger.debug(f"找到 {len(source_files)} 个源代码文件")
        return source_files
    
    def create_temp_copy(self) -> str:
        """创建项目的临时副本用于模型处理"""
        if self.temp_dir is None:
            self.temp_dir = tempfile.mkdtemp(prefix="model_eval_")
            logger.info(f"创建临时目录: {self.temp_dir}")
        
        # 复制项目文件
        for item in self.project_path.iterdir():
            if item.name.startswith('.'):
                continue
            dest = Path(self.temp_dir) / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        
        return self.temp_dir
    
    def cleanup_temp(self):
        """清理临时目录"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logger.info(f"清理临时目录: {self.temp_dir}")
            self.temp_dir = None


class ModelClient:
    """模型客户端，负责与AI模型API交互"""
    
    def __init__(self, base_url: str, token: str, model_name: str, retry_config: Optional[Dict[str, Any]] = None):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.model_name = model_name
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        self.retry_config = retry_config or {
            "max_retries": 3,
            "retry_delay": 1.0,
            "retry_backoff_factor": 2.0
        }
    
    def generate_code_changes(self, prompt: str, project_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成代码修改建议
        
        返回格式:
        {
            "model": model_name,
            "changes": [
                {
                    "file": "path/to/file",
                    "content": "new file content",
                    "description": "change description"
                }
            ],
            "explanation": "模型对修改的解释"
        }
        """
        # 构建请求消息
        messages = self._build_messages(prompt, project_info)
        
        # 调用API
        response = self._call_api(messages)
        
        # 解析响应
        return self._parse_response(response)
    
    def _build_messages(self, prompt: str, project_info: Dict[str, Any]) -> List[Dict[str, str]]:
        """构建API请求的消息"""
        system_message = """你是一个专业的软件工程师。请根据用户提供的项目信息和问题描述，给出具体的代码修改建议。
        你的响应应该包含：
        1. 对问题的分析
        2. 具体的代码修改（如果有多个文件，请分别说明）
        3. 修改后的完整文件内容（如果需要）
        4. 修改的解释
        
        请使用JSON格式返回，包含以下字段：
        - "analysis": 问题分析
        - "changes": 修改列表，每个修改包含"file", "content", "description"
        - "explanation": 整体解释
        """
        
        user_message = f"""项目信息：
- 项目路径: {project_info['path']}
- 是否为git仓库: {project_info['is_git_repo']}
- 当前分支: {project_info['current_branch']}
- 源代码文件: {', '.join(project_info['files'][:10])} (共{len(project_info['files'])}个文件)

问题描述：
{prompt}

请提供具体的代码修改建议。"""
        
        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
    
    def _call_api(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """调用模型API，支持重试"""
        url = f"{self.base_url}/chat/completions"
        data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4000
        }
        
        max_retries = self.retry_config["max_retries"]
        retry_delay = self.retry_config["retry_delay"]
        backoff_factor = self.retry_config["retry_backoff_factor"]
        
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(url, headers=self.headers, json=data, timeout=60)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.warning(f"API调用失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                if attempt < max_retries:
                    sleep_time = retry_delay * (backoff_factor ** attempt)
                    logger.info(f"等待 {sleep_time:.2f} 秒后重试...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"API调用达到最大重试次数，最终失败: {e}")
                    raise last_exception
        # 理论上不会执行到这里
        raise last_exception
    
    def _parse_response(self, api_response: Dict[str, Any]) -> Dict[str, Any]:
        """解析API响应"""
        # 这里需要根据实际API响应格式调整
        # 假设响应在choices[0].message.content中
        content = api_response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # 尝试解析JSON
        try:
            parsed = json.loads(content)
            parsed["model"] = self.model_name
            return parsed
        except json.JSONDecodeError:
            # 如果不是JSON，则作为纯文本处理
            return {
                "model": self.model_name,
                "analysis": "",
                "changes": [],
                "explanation": content,
                "raw_response": content
            }


class CodeApplier:
    """代码应用器，负责将模型建议的修改应用到项目"""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
    
    def apply_changes(self, changes: List[Dict[str, str]]) -> bool:
        """应用修改到项目文件"""
        success = True
        for change in changes:
            file_path = self.project_path / change["file"]
            content = change["content"]
            
            try:
                # 确保目录存在
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 写入新内容
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                file_size = len(content.encode('utf-8'))
                logger.info(f"已修改文件: {file_path} (大小: {file_size} 字节)")
            except Exception as e:
                logger.error(f"修改文件失败 {file_path}: {e}")
                success = False
        
        return success
    
    def create_patch(self, original_path: str, modified_path: str) -> str:
        """创建补丁文件"""
        try:
            result = subprocess.run(
                ["diff", "-u", original_path, modified_path],
                capture_output=True,
                text=True
            )
            return result.stdout
        except Exception as e:
            logger.error(f"创建补丁失败: {e}")
            return ""


class Evaluator:
    """评估器，使用DeepSeek模型对结果进行评分"""
    
    def __init__(self, model_client: ModelClient):
        self.model_client = model_client
    
    def evaluate(self, original_project: Dict[str, Any], 
                 model_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """评估所有模型的结果"""
        evaluated = []
        
        for result in model_results:
            score = self._score_result(original_project, result)
            result["score"] = score
            evaluated.append(result)
            logger.info(f"模型 {result.get('model', 'unknown')} 得分: {score}")
        
        return evaluated
    
    def _score_result(self, original_project: Dict[str, Any],
                      result: Dict[str, Any]) -> float:
        """对单个结果进行评分（0-100）"""
        # 构建评估提示
        prompt = self._build_evaluation_prompt(original_project, result)
        
        # 调用DeepSeek模型
        messages = [
            {"role": "system", "content": "你是一个代码质量评估专家。请根据提供的标准对代码修改进行评分。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.model_client._call_api(messages)
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            logger.debug(f"评分响应内容: {content[:200]}...")
            
            # 尝试从响应中提取分数
            match = re.search(r'\b(\d{1,3}(?:\.\d+)?)\b', content)
            if match:
                score = float(match.group(1))
                score = min(max(score, 0), 100)  # 限制在0-100之间
                logger.debug(f"提取分数: {score}")
                return score
            else:
                logger.warning("未能在响应中找到分数，使用默认分数 50.0")
                return 50.0  # 默认分数
        except Exception as e:
            logger.error(f"评分失败: {e}")
            return 0.0
    
    def _build_evaluation_prompt(self, original_project: Dict[str, Any], 
                                 result: Dict[str, Any]) -> str:
        """构建评估提示"""
        return f"""请对以下代码修改进行评分（0-100分）：

原始项目信息：
- 文件数量: {len(original_project.get('files', []))}
- 问题描述: {original_project.get('prompt', 'N/A')}

模型修改信息：
- 模型: {result.get('model', 'unknown')}
- 分析: {result.get('analysis', '无')}
- 修改数量: {len(result.get('changes', []))}
- 解释: {result.get('explanation', '无')}

请根据以下标准评分：
1. 问题解决的准确性（30%）
2. 代码质量（可读性、规范性）（30%）
3. 修改的完整性（是否覆盖所有相关文件）（20%）
4. 解释的清晰度（20%）

请只返回一个数字分数，不要有其他内容。"""


class GitManager:
    """Git管理器，负责代码合并与推送"""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
    
    def commit_changes(self, message: str) -> bool:
        """提交更改"""
        try:
            # 添加所有更改
            subprocess.run(
                ["git", "add", "."],
                cwd=self.project_path,
                check=True
            )
            
            # 提交
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.project_path,
                check=True
            )
            
            logger.info(f"已提交更改: {message}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"提交失败: {e}")
            return False
    
    def merge_to_main(self, branch_name: str) -> bool:
        """合并到main分支"""
        try:
            # 切换到main
            subprocess.run(
                ["git", "checkout", "main"],
                cwd=self.project_path,
                check=True
            )
            
            # 拉取最新
            subprocess.run(
                ["git", "pull"],
                cwd=self.project_path,
                check=True
            )
            
            # 合并
            subprocess.run(
                ["git", "merge", branch_name],
                cwd=self.project_path,
                check=True
            )
            
            logger.info(f"已合并分支 {branch_name} 到 main")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"合并失败: {e}")
            return False
    
    def push_to_github(self) -> bool:
        """推送到GitHub"""
        try:
            subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=self.project_path,
                check=True
            )
            
            logger.info("已推送到GitHub")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"推送失败: {e}")
            return False
    
    def create_branch(self, branch_name: str) -> bool:
        """创建新分支"""
        try:
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=self.project_path,
                check=True
            )
            logger.info(f"已创建分支: {branch_name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"创建分支失败: {e}")
            return False
    
    def generate_diff_to_main(self, branch_name: str) -> bool:
        """
        生成当前分支与main分支的差异，并写入detailed_code_diffs.txt文件
        
        参数:
            branch_name: 当前分支名称
            
        返回:
            bool: 是否成功生成差异文件
        """
        try:
            # 获取当前分支与main分支的差异
            result = subprocess.run(
                ["git", "diff", "main...{}".format(branch_name)],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True
            )
            diff_content = result.stdout
            
            # 如果diff为空，说明没有差异
            if not diff_content.strip():
                logger.info("当前分支与main分支无差异")
                diff_content = "# 当前分支与main分支无差异\n"
            
            # 写入文件
            diff_file_path = self.project_path / "detailed_code_diffs.txt"
            with open(diff_file_path, 'w', encoding='utf-8') as f:
                f.write(f"# 代码差异报告\n")
                f.write(f"# 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 分支: {branch_name} 与 main 的差异\n")
                f.write(f"# 命令: git diff main...{branch_name}\n")
                f.write("\n")
                f.write(diff_content)
            
            file_size = len(diff_content.encode('utf-8'))
            logger.info(f"差异文件已生成: {diff_file_path} (大小: {file_size} 字节)")
            return True
            
        except subprocess.CalledProcessError as e:
            # git diff可能返回非零退出码（例如没有共同祖先），尝试使用两个点的diff
            logger.warning(f"git diff main...{branch_name} 失败: {e}，尝试 git diff main..{branch_name}")
            try:
                result = subprocess.run(
                    ["git", "diff", "main..{}".format(branch_name)],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    check=False  # 不检查退出码，因为可能没有差异
                )
                diff_content = result.stdout
                
                if not diff_content.strip():
                    logger.info("当前分支与main分支无差异")
                    diff_content = "# 当前分支与main分支无差异\n"
                
                diff_file_path = self.project_path / "detailed_code_diffs.txt"
                with open(diff_file_path, 'w', encoding='utf-8') as f:
                    f.write(f"# 代码差异报告\n")
                    f.write(f"# 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"# 分支: {branch_name} 与 main 的差异\n")
                    f.write(f"# 命令: git diff main..{branch_name}\n")
                    f.write("\n")
                    f.write(diff_content)
                
                file_size = len(diff_content.encode('utf-8'))
                logger.info(f"差异文件已生成: {diff_file_path} (大小: {file_size} 字节)")
                return True
            except Exception as e2:
                logger.error(f"生成差异文件失败: {e2}")
                return False
        except Exception as e:
            logger.error(f"生成差异文件失败: {e}")
            return False


class MultiModelEvaluator:
    """主控制器，协调整个评估流程"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config_manager = ConfigManager(config_path)
        self.project_processor = None
        self.model_clients = {}
        self.evaluator = None
        self.git_manager = None
        
    def run(self):
        """运行整个评估流程"""
        logger.info("开始多模型评估流程")
        
        try:
            # 1. 加载配置
            config = self.config_manager.load()
            prompt = self.config_manager.get_prompt()
            base_url = self.config_manager.get_base_url()
            token = self.config_manager.get_token()
            model_names = self.config_manager.get_model_names()
            retry_config = self.config_manager.get_retry_config()
            
            # 2. 初始化项目处理器
            self.project_processor = ProjectProcessor()
            project_info = self.project_processor.get_project_info()
            project_info["prompt"] = prompt
            logger.info(f"项目信息: {project_info['path']}, 分支: {project_info['current_branch']}")
            
            # 3. 初始化模型客户端（排除DeepSeek，因为它用于评估）
            model_clients_to_evaluate = []
            for key, model_name in model_names.items():
                if key != "deepseek":
                    client = ModelClient(base_url, token, model_name, retry_config)
                    self.model_clients[key] = client
                    model_clients_to_evaluate.append((key, client))
            
            # 4. 为每个模型生成修改建议
            model_results = []
            for key, client in model_clients_to_evaluate:
                logger.info(f"正在使用模型 {key} ({client.model_name}) 生成修改建议...")
                try:
                    result = client.generate_code_changes(prompt, project_info)
                    model_results.append(result)
                    logger.info(f"模型 {key} 生成完成")
                except Exception as e:
                    logger.error(f"模型 {key} 处理失败: {e}")
            if not model_results:
                logger.error("所有模型处理失败，流程终止")
                return False
            
            # 5. 初始化评估器（使用DeepSeek模型）
            deepseek_client = ModelClient(base_url, token, model_names["deepseek"], retry_config)
            self.evaluator = Evaluator(deepseek_client)
            
            # 6. 评估所有模型结果
            evaluated_results = self.evaluator.evaluate(project_info, model_results)
            
            # 7. 选择得分最高的模型
            best_result = max(evaluated_results, key=lambda x: x.get("score", 0))
            logger.info(f"最佳模型: {best_result.get('model')}, 得分: {best_result.get('score')}")
            
            # 8. 应用最佳模型的修改
            if best_result.get("changes"):
                code_applier = CodeApplier(self.project_processor.project_path)
                success = code_applier.apply_changes(best_result["changes"])
                if not success:
                    logger.error("应用修改失败")
                    return False
                logger.info("最佳模型修改已应用")
            else:
                logger.warning("最佳模型没有提供具体修改")
            
            # 9. 生成分析报告
            self._generate_analysis_report(evaluated_results, best_result)
            
            # 10. 初始化Git管理器并提交更改
            self.git_manager = GitManager(self.project_processor.project_path)
            branch_name = f"model-eval-{int(time.time())}"
            
            if project_info["is_git_repo"]:
                if self.git_manager.create_branch(branch_name):
                    commit_message = f"feat: 应用模型 {best_result.get('model')} 的修改 (得分: {best_result.get('score')})"
                    if self.git_manager.commit_changes(commit_message):
                        # 在合并到main前生成代码差异报告
                        logger.info("正在生成代码差异报告...")
                        diff_success = self.git_manager.generate_diff_to_main(branch_name)
                        if diff_success:
                            logger.info("代码差异报告生成成功")
                        else:
                            logger.warning("代码差异报告生成失败，但继续流程")
                        
                        if self.git_manager.merge_to_main(branch_name):
                            self.git_manager.push_to_github()
                        else:
                            logger.warning("合并到main失败，跳过推送")
                    else:
                        logger.warning("提交更改失败，跳过合并")
                else:
                    logger.warning("创建分支失败，跳过Git操作")
            else:
                logger.info("项目不是git仓库，跳过Git操作")
            
            logger.info("多模型评估流程完成")
            return True
            
        except Exception as e:
            logger.error(f"流程执行失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _generate_analysis_report(self, evaluated_results, best_result):
        """生成分析报告analysis.md"""
        report_path = Path(self.project_processor.project_path) / "analysis.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# 多模型评估分析报告\n\n")
            f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## 评估结果汇总\n")
            f.write("| 模型 | 得分 | 修改数量 | 分析 |\n")
            f.write("|------|------|----------|------|\n")
            for result in evaluated_results:
                model = result.get('model', 'unknown')
                score = result.get('score', 0)
                changes_count = len(result.get('changes', []))
                analysis = result.get('analysis', '')[:100] + "..." if result.get('analysis') else "无"
                f.write(f"| {model} | {score:.2f} | {changes_count} | {analysis} |\n")
            
            f.write("\n## 最佳模型\n")
            f.write(f"- **模型**: {best_result.get('model')}\n")
            f.write(f"- **得分**: {best_result.get('score'):.2f}\n")
            f.write(f"- **分析**: {best_result.get('analysis', '无')}\n")
            f.write(f"- **解释**: {best_result.get('explanation', '无')}\n")
            
            f.write("\n## 修改详情\n")
            if best_result.get("changes"):
                for i, change in enumerate(best_result["changes"], 1):
                    f.write(f"### 修改 {i}: {change.get('file', '未知文件')}\n")
                    f.write(f"**描述**: {change.get('description', '无描述')}\n")
                    f.write("```\n")
                    f.write(change.get('content', '')[:500])
                    if len(change.get('content', '')) > 500:
                        f.write("\n... (内容过长，已截断)")
                    f.write("\n```\n\n")
            else:
                f.write("无具体修改内容\n")
            
            f.write("\n## 评估标准\n")
            f.write("1. 问题解决的准确性（30%）\n")
            f.write("2. 代码质量（可读性、规范性）（30%）\n")
            f.write("3. 修改的完整性（是否覆盖所有相关文件）（20%）\n")
            f.write("4. 解释的清晰度（20%）\n")
        
        logger.info(f"分析报告已生成: {report_path}")


def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(description='多模型评估与代码合并脚本')
    parser.add_argument('--config', default='config.json', help='配置文件路径')
    args = parser.parse_args()
    
    evaluator = MultiModelEvaluator(args.config)
    success = evaluator.run()
    
    if success:
        print("评估流程成功完成")
        sys.exit(0)
    else:
        print("评估流程失败")
        sys.exit(1)


if __name__ == "__main__":
    main()