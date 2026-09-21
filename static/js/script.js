// ===== QUIZ RENDERING (fetch via API) =====
document.querySelectorAll('.quiz-container').forEach(async container => {
    const contentId = container.dataset.contentId;
    try {
        const res = await fetch(`/api/quiz/${contentId}`);
        const data = await res.json();

        if (data.error || !data.quiz || data.quiz.length === 0) {
            container.innerHTML = '<p style="color:#888;">No quiz data available.</p>';
            return;
        }

        const quiz = data.quiz;
        let html = '';
        quiz.forEach((q, i) => {
            html += `<div class="quiz-question">`;
            html += `<p style="margin-top:15px;"><strong>Q${i + 1}: ${q.q}</strong></p>`;
            q.options.forEach(opt => {
                html += `<label class="quiz-option">
                    <input type="radio" name="q_${contentId}_${i}" value="${escapeAttr(opt)}">
                    <span>${opt}</span>
                </label>`;
            });
            html += `</div>`;
        });
        html += `<button class="btn-primary" style="margin-top:15px;" onclick="submitQuiz(${contentId}, ${quiz.length})">Submit Quiz</button>`;
        html += `<div id="quizResult_${contentId}" style="margin-top:15px;"></div>`;
        container.innerHTML = html;
    } catch (e) {
        console.error('Quiz load error:', e);
        container.innerHTML = '<p style="color:#dc2626;">Error loading quiz. Please refresh.</p>';
    }
});

function escapeAttr(str) {
    return String(str).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function submitQuiz(contentId, total) {
    const answers = {};
    for (let i = 0; i < total; i++) {
        const sel = document.querySelector(`input[name="q_${contentId}_${i}"]:checked`);
        if (sel) answers[i] = sel.value;
    }
    if (Object.keys(answers).length < total) {
        if (!confirm('You have unanswered questions. Submit anyway?')) return;
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
                    <p style="margin:0 0 5px;"><strong>Q${i + 1}: ${d.question}</strong></p>
                    <p style="margin:0;font-size:0.9rem;">Your answer: <span style="color:${color};">${icon} ${d.user_answer || '(not answered)'}</span></p>
                    ${!d.is_correct ? `<p style="margin:0;font-size:0.9rem;">Correct: <span style="color:#16a34a;">✅ ${d.correct_answer}</span></p>` : ''}
                </div>`;
            });
            html += '</div>';
        }

        if (data.certificate_issued) {
            html += `<div style="margin-top:15px;padding:15px;background:#fef3c7;border-radius:8px;border-left:4px solid #f59e0b;">
                🎓 <strong>Certificate issued!</strong> Check <a href="/my-certificates">My Certificates</a>.
            </div>`;
        }

        document.getElementById(`quizResult_${contentId}`).innerHTML = html;
    })
    .catch(err => {
        console.error('Quiz submit error:', err);
        alert('Error submitting quiz. Please try again.');
    });
}