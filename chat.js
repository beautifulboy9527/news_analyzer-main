document.querySelectorAll('.chat-bubble').forEach(bubble => {
    const text = bubble.textContent || bubble.innerText;
    const maxWidth = 300; // 气泡框最大宽度
    const padding = 30; // 气泡框左右内边距
    const context = document.createElement('canvas').getContext('2d');
    context.font = getComputedStyle(bubble).font; // 获取气泡字体样式
    const textWidth = context.measureText(text).width;
    bubble.style.width = Math.min(textWidth + padding, maxWidth) + 'px';
});
