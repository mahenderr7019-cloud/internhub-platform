// ===== QUIZ RENDERING =====
document.querySelectorAll('.quiz').forEach(quizEl => {
    const quiz = JSON.parse(quizEl.dataset.quiz || '[]');
    const contentId = quizEl.dataset.contentId;
    let html = '';
    quiz.forEach((q, i) => {
        html += `<p style="margin-top:15px;"><strong>Q${i + 1}: ${q.q}</strong></p>`;
        q.options.forEach(opt => {
            html += `<label style="display:block;margin:5px 0;">
                <input type="radio" name="q_${contentId}_${i}" value="${opt.replace(/"/g, '&quot;')}"> ${opt}
            </label>`;
        });
    });
    html += `<button class="btn-primary" style="margin-top:15px;" onclick="submitQuiz(${contentId}, ${quiz.length})">Submit Quiz</button>`;
    html += `<div id="quizResult_${contentId}" style="margin-top:15px;"></div>`;
    quizEl.innerHTML = html;
});

function submitQuiz(contentId, total) {
    const answers = {};
    for (let i = 0; i < total; i++) {
        const sel = document.querySelector(`input[name="q_${contentId}_${i}"]:checked`);
        if (sel) answers[i] = sel.value;
    }
    fetch(`/mark_complete/${contentId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(answers)
    })
    .then(r => r.json())
    .then(data => {
        const pct = Math.round((data.score / total) * 100);
        let html = `<div style="background:#f0fdf4;padding:15px;border-radius:8px;border-left:4px solid #16a34a;">
            <h3 style="color:#16a34a;margin:0 0 5px;">Score: ${data.score} / ${total} (${pct}%)</h3>
            <p style="margin:0;color:#555;">${pct >= 70 ? '🎉 Great job!' : '📚 Keep learning!'}</p>
        </div>`;
        if (data.details && data.details.length > 0) {
            html += '<div style="margin-top:15px;"><h4>Detailed Results:</h4>';
            data.details.forEach((d, i) => {
                const color = d.is_correct ? '#16a34a' : '#dc2626';
                const icon = d.is_correct ? '✅' : '❌';
                html += `<div style="padding:10px;background:#fff;border-radius:6px;margin-bottom:8px;border-left:3px solid ${color};">
                    <p style="margin:0 0 5px;"><strong>Q${i+1}: ${d.question}</strong></p>
                    <p style="margin:0;font-size:0.9rem;">Your answer: <span style="color:${color};">${icon} ${d.user_answer || '(not answered)'}</span></p>
                    ${!d.is_correct ? `<p style="margin:0;font-size:0.9rem;">Correct answer: <span style="color:#16a34a;">✅ ${d.correct_answer}</span></p>` : ''}
                </div>`;
            });
            html += '</div>';
        }
        document.getElementById(`quizResult_${contentId}`).innerHTML = html;
    });
}

// ===== YOUTUBE VIDEO TRACKING =====
const videoPlayers = {};   // contentId -> YT.Player
const videoWatched = {};   // contentId -> bool

function onYouTubeIframeAPIReady() {
    document.querySelectorAll('.video-tracker').forEach(el => {
        const contentId = el.dataset.contentId;
        const videoUrl = el.dataset.videoUrl;
        const videoId = extractYoutubeId(videoUrl);
        if (!videoId) return;

        videoPlayers[contentId] = new YT.Player(`player_${contentId}`, {
            videoId: videoId,
            playerVars: {
                'rel': 0,
                'modestbranding': 1,
                'controls': 1,
                'disablekb': 0
            },
            events: {
                'onStateChange': (e) => onPlayerStateChange(e, contentId)
            }
        });
    });
}

function extractYoutubeId(url) {
    if (!url) return null;
    let m = url.match(/embed\/([A-Za-z0-9_-]{6,})/);
    if (m) return m[1];
    m = url.match(/youtu\.be\/([A-Za-z0-9_-]{6,})/);
    if (m) return m[1];
    m = url.match(/[?&]v=([A-Za-z0-9_-]{6,})/);
    if (m) return m[1];
    return null;
}

function onPlayerStateChange(event, contentId) {
    // YT.PlayerState.ENDED = 0
    if (event.data === 0) {
        videoWatched[contentId] = true;
        const status = document.getElementById(`status_${contentId}`);
        const btn = document.getElementById(`markBtn_${contentId}`);
        if (status) status.innerHTML = '✅ Video completed! Click "Mark as Watched" to save.';
        if (btn) btn.disabled = false;
    }
}

// Prevent marking before video is watched
function markVideoWatched(contentId) {
    if (!videoWatched[contentId]) {
        alert('⚠️ Please watch the full video first.');
        return;
    }
    fetch(`/mark_complete/${contentId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_watched: true })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            const status = document.getElementById(`status_${contentId}`);
            const btn = document.getElementById(`markBtn_${contentId}`);
            if (status) status.innerHTML = '✅ Completed!';
            if (btn) { btn.disabled = true; btn.innerHTML = '✅ Already Marked'; }
        }
    });
}

// If API loads before our elements, call once anyway
window.addEventListener('load', () => {
    if (typeof YT !== 'undefined' && YT.Player) {
        // API already ready
        if (!Object.keys(videoPlayers).length) onYouTubeIframeAPIReady();
    }
});