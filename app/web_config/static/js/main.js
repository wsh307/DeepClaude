document.addEventListener('DOMContentLoaded', function() {
    // 全局变量
    const configData = {};
    const apiPath = window.location.pathname;
    const apiBasePath = `${apiPath}/api`;
    
    // DOM 元素
    const saveBtn = document.getElementById('save-btn');
    const resetBtn = document.getElementById('reset-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const messageBox = document.getElementById('message-box');
    const navLinks = document.querySelectorAll('nav a');
    const sections = document.querySelectorAll('.config-section');
    const togglePasswordBtns = document.querySelectorAll('.toggle-password');
    
    // 初始化
    fetchConfig();
    
    // 事件监听
    saveBtn.addEventListener('click', saveConfig);
    resetBtn.addEventListener('click', resetForm);
    logoutBtn.addEventListener('click', logout);
    
    // 导航切换
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const target = this.getAttribute('href').substring(1);
            
            // 更新导航状态
            navLinks.forEach(el => el.classList.remove('active'));
            this.classList.add('active');
            
            // 更新内容区域
            sections.forEach(section => {
                if (section.id === target) {
                    section.classList.remove('hidden');
                } else {
                    section.classList.add('hidden');
                }
            });
        });
    });
    
    // 密码显示/隐藏切换
    togglePasswordBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const input = this.previousElementSibling;
            if (input.type === 'password') {
                input.type = 'text';
                this.textContent = '隐藏';
            } else {
                input.type = 'password';
                this.textContent = '显示';
            }
        });
    });
    
    // 获取配置
    async function fetchConfig() {
        try {
            const response = await fetch(`${apiBasePath}/config`, {
                credentials: 'include'  // 重要：包含 cookies
            });
            
            if (response.ok) {
                configData = await response.json();
                populateForm(configData);
                console.log("配置加载成功");
            } else if (response.status === 401) {
                window.location.href = `${apiPath}/login`;
            } else {
                showMessage("加载配置失败: " + response.statusText, "error");
            }
        } catch (error) {
            showMessage("获取配置时发生错误: " + error.message, "error");
        }
    }
    
    // 填充表单
    function populateForm(data) {
        // API 密钥
        document.getElementById('allow-api-key').value = data.api_keys?.allow_api_key || '';
        document.getElementById('deepseek-api-key').value = data.api_keys?.deepseek || '';
        document.getElementById('claude-api-key').value = data.api_keys?.claude || '';
        document.getElementById('openai-composite-api-key').value = data.api_keys?.openai_composite || '';
        
        // 端点
        document.getElementById('deepseek-endpoint').value = data.endpoints?.deepseek || '';
        document.getElementById('claude-endpoint').value = data.endpoints?.claude || '';
        document.getElementById('openai-composite-endpoint').value = data.endpoints?.openai_composite || '';
        
        // 模型
        document.getElementById('deepseek-model').value = data.models?.deepseek || '';
        document.getElementById('claude-model').value = data.models?.claude || '';
        document.getElementById('openai-composite-model').value = data.models?.openai_composite || '';
        document.getElementById('claude-provider').value = data.providers?.claude || 'anthropic';
        
        // 选项
        document.getElementById('allow-origins').value = data.options?.allow_origins || '*';
        document.getElementById('is-origin-reasoning').value = data.options?.is_origin_reasoning === true ? 'true' : 'false';
        document.getElementById('log-level').value = data.options?.log_level || 'INFO';
    }
    
    // 收集表单数据
    function collectFormData() {
        const data = {
            api_keys: {
                allow_api_key: document.getElementById('allow-api-key').value.trim(),
                deepseek: document.getElementById('deepseek-api-key').value.trim(),
                claude: document.getElementById('claude-api-key').value.trim(),
                openai_composite: document.getElementById('openai-composite-api-key').value.trim()
            },
            endpoints: {
                deepseek: document.getElementById('deepseek-endpoint').value.trim(),
                claude: document.getElementById('claude-endpoint').value.trim(),
                openai_composite: document.getElementById('openai-composite-endpoint').value.trim()
            },
            models: {
                deepseek: document.getElementById('deepseek-model').value.trim(),
                claude: document.getElementById('claude-model').value.trim(),
                openai_composite: document.getElementById('openai-composite-model').value.trim()
            },
            providers: {
                claude: document.getElementById('claude-provider').value
            },
            options: {
                allow_origins: document.getElementById('allow-origins').value.trim(),
                is_origin_reasoning: document.getElementById('is-origin-reasoning').value === 'true',
                log_level: document.getElementById('log-level').value
            }
        };
        
        return data;
    }
    
    // 保存配置
    async function saveConfig() {
        const formData = collectFormData();

        try {
            const response = await fetch(`${apiBasePath}/config`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                credentials: 'include',  // 重要：包含 cookies
                body: JSON.stringify(formData),
            });

            if (response.ok) {
                showMessage("配置已成功保存！", "success");
                configData = formData;
                allInputs.forEach((input) => {
                    input.classList.remove("modified");
                });
            } else if (response.status === 401) {
                window.location.href = `${apiPath}/login`;
            } else {
                const error = await response.json();
                showMessage("保存配置失败: " + (error.message || response.statusText), "error");
            }
        } catch (error) {
            showMessage("保存配置时发生错误: " + error.message, "error");
        }
    }
    
    // 重置表单
    function resetForm() {
        populateForm(configData);
        showMessage('表单已重置为当前配置', 'info');
    }
    
    // 退出登录
    async function logout() {
        try {
            await fetch(`${apiBasePath}/logout`, {
                method: 'POST',
                credentials: 'include'
            });
        } catch (error) {
            console.error('登出时发生错误:', error);
        } finally {
            window.location.href = `${apiPath}/login`;
        }
    }
    
    // 显示消息
    function showMessage(message, type = 'info') {
        messageBox.textContent = message;
        messageBox.className = type;
        messageBox.classList.remove('hidden');
        
        // 5秒后自动隐藏
        setTimeout(() => {
            messageBox.classList.add('hidden');
        }, 5000);
    }
}); 