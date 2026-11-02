// Replace contact with a real channel when ready.
// { type: 'email' | 'wechat' | 'url', value: '...', label: '...' }
const profile = {
  name: '汪泽雨',
  role: 'AI 产品经理',
  introduction: '你好，我是汪泽雨，一名 AI 产品经理。在人的需求与技术的边界之间，探索更自然、更有价值的智能体验。',
  contact: { type: '', value: '', label: '' }
};

const explorations = {
  knowledge: {
    title: '让知识找到你',
    category: '知识管理 × RAG',
    lead: '一个个人知识助手的概念：让收藏过、读过、写过的资料，在需要时重新发挥价值。',
    problem: '资料越积越多，却常常想不起存在哪里。即使检索到相关文档，也需要花时间判断内容是否能回答眼前的问题。',
    idea: '围绕个人资料库提供自然语言检索，把答案与原文片段放在一起；当资料不足时，明确说明哪些问题还没有依据。',
    decisions: ['先定位资料来源，再组织答案，保留回看原文的入口。', '区分原文事实与模型整理，减少“看起来正确”的误导。', '以“找到有用资料”为核心任务，避免添加无关功能。'],
    validation: '用同一组检索任务，对比关键词搜索与问答原型，观察找到有效信息所需的步骤，以及用户能否判断答案来源。'
  },
  agent: {
    title: '从对话到行动',
    category: 'AI Agent × 工作流',
    lead: '一个任务协作助手的概念：让 AI 理解目标、提出计划，并在人的判断下逐步推进。',
    problem: '一次对话可以给出建议，但完成一项工作通常还需要拆解任务、使用工具、检查结果。用户也很难判断 AI 正在做什么。',
    idea: '把任务执行过程变成清晰的步骤视图，展示当前进度、下一步行动和需要用户决定的事项。',
    decisions: ['执行前展示计划，允许用户调整范围与优先级。', '关键操作由用户确认，并提供暂停和修改入口。', '明确区分进行中、已完成与失败状态，让错误可恢复。'],
    validation: '选取一个范围清楚的小任务进行原型测试，观察用户是否理解执行状态，以及遇到偏差时能否顺利调整计划。'
  },
  evaluation: {
    title: '定义什么是好用',
    category: '产品体验 × 评测',
    lead: '一个 AI 产品体验观察台的概念：让“感觉更好”变成可以讨论、比较和改进的具体问题。',
    problem: 'AI 输出具有不确定性，仅凭少量演示很难判断体验。不同的人对“好用”的理解也可能完全不同。',
    idea: '从具体场景建立体验评测任务，分别观察是否有用、是否可信、是否易用，保留每一次判断的依据。',
    decisions: ['先定义真实任务和成功标准，再讨论分数。', '把模型回答与完整交互过程放在一起观察。', '记录失败样本和使用场景，让评测能够指导下一轮改进。'],
    validation: '邀请不同体验者完成同一组任务，对比评价的一致性；检查评测结论是否能指出具体的产品改进方向。'
  }
};

const siteHeader = document.querySelector('#site-header');
if (siteHeader) {
  const updateHeader = () => siteHeader.classList.toggle('is-scrolled', window.scrollY > 12);
  window.addEventListener('scroll', updateHeader, { passive: true });
  updateHeader();
}

const projectTabs = document.querySelector('#project-tabs');
if (projectTabs) {
  const tabs = [...projectTabs.querySelectorAll('[role="tab"]')];
  const activateTab = (activeTab, moveFocus = false) => {
    tabs.forEach(tab => {
      const selected = tab === activeTab;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      const panel = document.getElementById(tab.getAttribute('aria-controls'));
      if (panel) panel.hidden = !selected;
    });
    if (moveFocus) activeTab.focus({ preventScroll: true });
  };

  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => activateTab(tab));
    tab.addEventListener('keydown', event => {
      let nextIndex;
      switch (event.key) {
        case 'ArrowRight': nextIndex = (index + 1) % tabs.length; break;
        case 'ArrowLeft': nextIndex = (index - 1 + tabs.length) % tabs.length; break;
        case 'Home': nextIndex = 0; break;
        case 'End': nextIndex = tabs.length - 1; break;
        default: return;
      }
      event.preventDefault();
      activateTab(tabs[nextIndex], true);
    });
  });

  const initialTab = tabs.find(tab => tab.getAttribute('aria-selected') === 'true') || tabs[0];
  if (initialTab) activateTab(initialTab);
}

const menuToggle = document.querySelector('.menu-toggle');
const mobileNav = document.querySelector('#mobile-nav');
function closeMenu() {
  menuToggle.setAttribute('aria-expanded', 'false');
  menuToggle.setAttribute('aria-label', '展开导航');
  mobileNav.hidden = true;
}
menuToggle.addEventListener('click', () => {
  const isOpen = menuToggle.getAttribute('aria-expanded') === 'true';
  mobileNav.hidden = isOpen;
  menuToggle.setAttribute('aria-expanded', String(!isOpen));
  menuToggle.setAttribute('aria-label', isOpen ? '展开导航' : '收起导航');
});
mobileNav.querySelectorAll('a').forEach(link => link.addEventListener('click', closeMenu));
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && !mobileNav.hidden) {
    closeMenu();
    menuToggle.focus();
  }
});
document.addEventListener('click', event => {
  if (!mobileNav.hidden && !event.target.closest('.header')) closeMenu();
});
matchMedia('(min-width: 601px)').addEventListener('change', event => {
  if (event.matches) closeMenu();
});

const projectDialog = document.querySelector('#project-dialog');
let activeProjectButton = null;
document.querySelectorAll('[data-project]').forEach(button => {
  button.addEventListener('click', () => {
    const project = explorations[button.dataset.project];
    if (!project) return;
    activeProjectButton = button;
    const content = document.querySelector('#dialog-content');
    content.replaceChildren();
    const badge = document.createElement('span');
    badge.className = 'dialog-badge';
    badge.textContent = project.category;
    const title = document.createElement('h2');
    title.id = 'dialog-title';
    title.textContent = project.title;
    const lead = document.createElement('p');
    lead.className = 'dialog-lead';
    lead.textContent = project.lead;
    content.append(badge, title, lead);
    [['看到的问题', project.problem], ['概念方向', project.idea], ['关键体验设计', project.decisions], ['如何验证', project.validation]].forEach(([heading, value]) => {
      const section = document.createElement('section');
      section.className = 'dialog-section';
      const h3 = document.createElement('h3');
      h3.textContent = heading;
      section.append(h3);
      if (Array.isArray(value)) {
        const list = document.createElement('ul');
        value.forEach(item => {
          const li = document.createElement('li');
          li.textContent = item;
          list.append(li);
        });
        section.append(list);
      } else {
        const p = document.createElement('p');
        p.textContent = value;
        section.append(p);
      }
      content.append(section);
    });
    projectDialog.showModal();
    projectDialog.scrollTop = 0;
    document.body.classList.add('modal-open');
  });
});
document.querySelectorAll('.dialog-close, .dialog-done').forEach(button => button.addEventListener('click', () => projectDialog.close()));
projectDialog.addEventListener('click', event => {
  const rect = projectDialog.getBoundingClientRect();
  if (event.target === projectDialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) projectDialog.close();
});
projectDialog.addEventListener('close', () => {
  document.body.classList.remove('modal-open');
  activeProjectButton?.focus({ preventScroll: true });
});

let toastTimeout;
function showToast(message) {
  clearTimeout(toastTimeout);
  const toast = document.querySelector('#toast');
  toast.textContent = message;
  toast.classList.add('visible');
  toastTimeout = setTimeout(() => toast.classList.remove('visible'), 3200);
}
async function copyText(text, message) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
    } else {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.cssText = 'position:fixed;top:-9999px;';
      document.body.append(textarea);
      textarea.select();
      const success = document.execCommand('copy');
      textarea.remove();
      if (!success) throw new Error('Copy unavailable');
    }
    showToast(message);
  } catch {
    showToast('暂时无法自动复制，请选中页面中的个人介绍复制。');
  }
}
document.querySelector('#copy-intro').addEventListener('click', () => copyText(profile.introduction, '个人介绍已复制'));
document.querySelector('#year').textContent = String(new Date().getFullYear());

const contact = profile.contact;
if (contact.value) {
  const container = document.querySelector('#contact-channel');
  const element = document.createElement(contact.type === 'wechat' ? 'button' : 'a');
  element.className = 'contact-real';
  element.textContent = contact.label || contact.value;
  let valid = false;
  if (contact.type === 'email' && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contact.value)) {
    element.href = `mailto:${contact.value}`;
    valid = true;
  } else if (contact.type === 'url') {
    try {
      const url = new URL(contact.value);
      if (url.protocol === 'https:') {
        element.href = url.href;
        element.target = '_blank';
        element.rel = 'noopener noreferrer';
        valid = true;
      }
    } catch { /* Keep the pending state for an invalid URL. */ }
  } else if (contact.type === 'wechat') {
    element.setAttribute('aria-label', `复制微信号 ${contact.value}`);
    element.addEventListener('click', () => copyText(contact.value, '微信号已复制'));
    valid = true;
  }
  if (valid) container.replaceChildren(element);
}
