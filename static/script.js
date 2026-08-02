document.addEventListener("DOMContentLoaded", () => {
    const loginScreen = document.getElementById("loginScreen");
    const mainApp = document.getElementById("mainApp");
    
    if (sessionStorage.getItem("tm_token")) {
      if(loginScreen) loginScreen.style.display = "none";
      if(mainApp) mainApp.style.display = "flex";
    } else {
      if(loginScreen) loginScreen.style.display = "flex";
      if(mainApp) mainApp.style.display = "none";
    }

    const loginBtn = document.getElementById("loginBtn");
    const loginUsername = document.getElementById("loginUsername");
    const loginPassword = document.getElementById("loginPassword");
    const loginError = document.getElementById("loginError");

    const hideError = () => { if(loginError) loginError.style.display = "none"; };
    if(loginUsername) loginUsername.addEventListener("input", hideError);
    if(loginPassword) loginPassword.addEventListener("input", hideError);

    if(loginBtn) {
      loginBtn.addEventListener("click", async () => {
        const username = loginUsername.value.trim();
        const password = loginPassword.value;
        if (!username || !password) return;

        loginBtn.disabled = true;
        loginBtn.textContent = "Logging in...";
        
        try {
          const res = await fetch("/api/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
          });
          
          if (res.ok) {
            const data = await res.json();
            sessionStorage.setItem("tm_token", data.token);
            loginScreen.style.display = "none";
            mainApp.style.display = "flex";
          } else {
            loginError.style.display = "block";
            loginError.textContent = "Invalid username or password";
          }
        } catch (err) {
          console.error(err);
          loginError.style.display = "block";
          loginError.textContent = "Network error";
        } finally {
          loginBtn.disabled = false;
          loginBtn.textContent = "Login";
        }
      });

      if(loginPassword) {
        loginPassword.addEventListener("keyup", (e) => {
          if (e.key === "Enter") loginBtn.click();
        });
      }
    }
  });

    // ── Screen Wake Lock ────────────────────────────────────
    let wakeLock = null;

    async function requestWakeLock() {
      if ('wakeLock' in navigator) {
        try {
          wakeLock = await navigator.wakeLock.request('screen');
          console.log('[Wake Lock] Acquired — screen will stay on.');

          wakeLock.addEventListener('release', () => {
            console.log('[Wake Lock] Released.');
            wakeLock = null;
          });
        } catch (err) {
          console.warn('[Wake Lock] Failed to acquire:', err.message);
          wakeLock = null;
        }
      }
    }

    async function releaseWakeLock() {
      if (wakeLock) {
        try {
          await wakeLock.release();
          console.log('[Wake Lock] Explicitly released.');
        } catch (err) {
          console.warn('[Wake Lock] Release failed:', err.message);
        }
        wakeLock = null;
      }
    }

    function dismissTermsBanner() {
      const banner = document.getElementById('termsBanner');
      if (banner) {
        banner.style.opacity = '0';
        banner.style.transform = 'translateY(-10px)';
        banner.style.transition = 'all 0.3s ease';
        setTimeout(() => banner.remove(), 300);
        localStorage.setItem('tm_terms_dismissed', '1');
      }
    }

    // Auto-hide if previously dismissed
    if (localStorage.getItem('tm_terms_dismissed') === '1') {
      const banner = document.getElementById('termsBanner');
      if (banner) banner.remove();
    }
    const elements = {
      claimInput: document.getElementById("claimInput"),
      verifyBtn: document.getElementById("verifyBtn"),
      verifyLoader: document.getElementById("verifyLoader"),
      btnText: document.querySelector(".btn-text"),
      loadingStatus: document.getElementById("loadingStatus"),
      initialState: document.getElementById("initialState"),
      dashboard: document.getElementById("dashboard"),
      
      pipelineTracker: document.getElementById("pipelineTracker"),
      
      verdictBanner: document.getElementById("verdictBanner"),
      verdictClaim: document.getElementById("verdictClaim"),
      verdictValue: document.getElementById("verdictValue"),
      verdictOneLine: document.getElementById("verdictOneLine"),
      confidenceBadge: document.getElementById("confidenceBadge"),
      
      fullReasoning: document.getElementById("fullReasoning"),
      whatIsTrue: document.getElementById("whatIsTrue"),
      whatIsFalse: document.getElementById("whatIsFalse"),
      whatIsUnclear: document.getElementById("whatIsUnclear"),
      
      blocGrid: document.getElementById("blocGrid"),
      hiddenStoriesContainer: document.getElementById("hiddenStoriesContainer")
    };

    // Re-acquire wake lock when user switches back to the tab during verification
    document.addEventListener('visibilitychange', async () => {
      if (document.visibilityState === 'visible' && wakeLock === null) {
        const isRunning = elements.verifyBtn.disabled;
        if (isRunning) {
          await requestWakeLock();
        }
      }
    });

    elements.verifyBtn.addEventListener("click", verifyClaim);
    elements.claimInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") verifyClaim();
    });

    // Toggle Accordion function
    window.toggleAccordion = function(element) {
      const parent = element.parentElement;
      parent.classList.toggle('active');
    };

    function toggleBackgroundSources() {
      const accordion = document.getElementById("backgroundAccordion");
      const label = document.getElementById("backgroundToggleLabel");
      const isActive = accordion.classList.contains("active");

      if (isActive) {
          accordion.classList.remove("active");
          label.textContent = "∨";
      } else {
          accordion.classList.add("active");
          label.textContent = "∧";
      }
    }

    function toggleSourceCard(btn) {
      const row = btn.closest('tr');
      const isExpanded = row.classList.contains('expanded');
      if (isExpanded) {
        row.classList.remove('expanded');
        btn.textContent = 'Show more ▼';
      } else {
        row.classList.add('expanded');
        btn.textContent = 'Show less ▲';
      }
    }

    function showErrorPanel(detail) {
        // Hide the dashboard and initial state if visible
        elements.dashboard.style.display = "none";
        document.getElementById('skeletonContainer').style.display = 'none';
        const rc = document.getElementById('resultsContainer');
        if (rc) rc.style.display = "none";

        // Show or reuse the error panel
        let errorPanel = document.getElementById("errorPanel");
        if (!errorPanel) {
            errorPanel = document.createElement("div");
            errorPanel.id = "errorPanel";
            // Insert it into main-content, after the top-bar
            const mainContent = document.querySelector(".main-content");
            mainContent.appendChild(errorPanel);
        }

        errorPanel.style.display = "flex";
        errorPanel.innerHTML = `
            <div class="error-panel-icon">✕</div>
            <div class="error-panel-body">
                <div class="error-panel-title">Something went wrong</div>
                <div class="error-panel-msg">
                    An error occurred while verifying this claim. Please try
                    again. If the problem persists, refresh the page and
                    resubmit.
                </div>
                <div class="error-panel-detail">${detail || ""}</div>
                <button class="btn btn-primary error-panel-retry"
                        onclick="dismissError()">
                    Try Again
                </button>
            </div>
        `;
    }

    function dismissError() {
        const errorPanel = document.getElementById("errorPanel");
        if (errorPanel) errorPanel.style.display = "none";
        elements.initialState.style.display = "block";
    }

    function buildSourceRow(sa) {
      const stance = sa.stance || "UNKNOWN";
      let sColor = "var(--text-muted)";
      let barColor = "var(--text-muted)";
      if (stance === "SUPPORTS") { sColor = "var(--success)"; barColor = "var(--success)"; }
      if (stance === "CONTRADICTS") { sColor = "var(--danger)"; barColor = "var(--danger)"; }
      if (stance === "PARTIALLY_SUPPORTS") { sColor = "var(--warning)"; barColor = "var(--warning)"; }

      let confidenceStr = 'N/A';
      let confidencePct = 0;
      if (typeof sa.stance_confidence === 'number') {
        confidencePct = Math.round(sa.stance_confidence * 100);
        if (sa.stance_confidence >= 0.8) confidenceStr = 'Very High';
        else if (sa.stance_confidence >= 0.6) confidenceStr = 'High';
        else if (sa.stance_confidence >= 0.4) confidenceStr = 'Medium';
        else if (sa.stance_confidence >= 0.2) confidenceStr = 'Low';
        else confidenceStr = 'Very Low';
      }

      return `
        <tr>
          <td>
            <div style="font-weight: 600; color: var(--text-main); margin-bottom: 0.25rem;">${sa.source_name || "Unknown"}</div>
            <a href="${sa.url || "#"}" target="_blank"
               style="font-size: 0.8rem; color: var(--accent); text-decoration: none;">
              View Source ↗
            </a>
            ${sa.archive_url ? `<br><a href="${sa.archive_url}" target="_blank" style="font-size: 0.75rem; color: var(--warning); text-decoration: none;">View Archive ↗</a>` : ''}
          </td>
          <td>${sa.alignment || "Unknown"}</td>
          <td>
            <span class="bloc-stance" style="background: rgba(255,255,255,0.05); color: ${sColor}; padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.7rem;">
              ${stance.replace('_', ' ')}
            </span>
          </td>
          <td>
            <div class="confidence-cell">
              <div class="confidence-bar-bg">
                <div class="confidence-bar-fill" style="width: ${confidencePct}%; background: ${barColor};"></div>
              </div>
              <span class="conf-label">${confidenceStr}</span>
            </div>
          </td>
          <td style="font-size: 0.85rem; color: var(--text-muted); max-width: 300px; line-height: 1.5;">
            ${sa.what_emphasized || "N/A"}
          </td>
          <td class="source-card-toggle-cell">
            <button class="source-card-toggle" onclick="toggleSourceCard(this)">
              Show more ▼
            </button>
          </td>
        </tr>
      `;
    }

    async function verifyClaim() {
      const claim = elements.claimInput.value.trim();
      if (!claim) return;

      // Acquire wake lock to keep screen on during 2–4 min verification
      await requestWakeLock();

      elements.btnText.style.display = "none";
      elements.verifyLoader.style.display = "block";
      elements.verifyBtn.disabled = true;


      // Show skeleton and pipeline tracker
      elements.dashboard.style.display = 'grid';
      document.getElementById('skeletonContainer').style.display = 'block';
      const rc = document.getElementById('resultsContainer');
      if (rc) rc.style.display = 'none';
      elements.pipelineTracker.style.display = 'block';
      
      elements.loadingStatus.style.fontSize = '0.75rem';
      elements.loadingStatus.style.opacity = '0.5';

      const STAGE_MESSAGES = {
        "idle": "Initializing...",
        "classifying": "Classifying claim scope...",
        "decomposing": "Breaking down claim...",
        "querying": "Generating search queries...",
        "retrieving": "Fetching global sources...",
        "analyzing_sources": "Analyzing source stances...",
        "synthesizing_perspectives": "Synthesizing media blocs...",
        "extracting_stories": "Extracting hidden narratives...",
        "generating_verdict": "Calculating final verdict..."
      };

      const FUN_MESSAGES = [
        "Still thinking...",
        "Reading between the lines...",
        "Decoding diplomatic speak...",
        "Cross-referencing state media...",
        "Following the money...",
        "Checking bias filters...",
        "Synthesizing the truth..."
      ];

      let currentStage = "idle";
      let stageCounter = 0;
      let funMsgIdx = 0;

      const requestId = crypto.randomUUID();

      // Update pipeline tracker
      const PIPELINE_ORDER = ["classifying", "decomposing", "retrieving", "analyzing_sources", "generating_verdict"];
      // Map backend stages to pipeline display stages
      const STAGE_MAP = {
        "classifying": "classifying",
        "decomposing": "decomposing",
        "querying": "retrieving",
        "retrieving": "retrieving",
        "analyzing_sources": "analyzing_sources",
        "synthesizing_perspectives": "analyzing_sources",
        "extracting_stories": "analyzing_sources",
        "generating_verdict": "generating_verdict"
      };

      function updatePipelineTracker(backendStage) {
        const mappedStage = STAGE_MAP[backendStage] || backendStage;
        const steps = document.querySelectorAll('.pipeline-step');
        const currentIdx = PIPELINE_ORDER.indexOf(mappedStage);
        
        steps.forEach((step, idx) => {
          step.classList.remove('active', 'completed');
          const textEl = step.querySelector('.step-text');
          const originalText = textEl.getAttribute('data-text') || textEl.textContent;
          textEl.setAttribute('data-text', originalText.replace(/\.\.\.$/, ''));
          
          if (idx < currentIdx) {
            step.classList.add('completed');
            step.querySelector('.step-indicator').textContent = '◉';
            textEl.textContent = textEl.getAttribute('data-text');
          } else if (idx === currentIdx) {
            step.classList.add('active');
            step.querySelector('.step-indicator').textContent = '○';
            textEl.textContent = textEl.getAttribute('data-text') + '...';
          } else {
            step.querySelector('.step-indicator').textContent = '○';
            textEl.textContent = textEl.getAttribute('data-text');
          }
        });
      }

      const pollStatus = async () => {
        try {
          const token = sessionStorage.getItem("tm_token");
          const res = await fetch("/api/status?request_id=" + requestId, {
            headers: { "Authorization": "Bearer " + token }
          });
          if (res.status === 401) {
            sessionStorage.removeItem("tm_token");
            window.location.reload();
            return;
          }
          if (res.ok) {
            const data = await res.json();
            if (data.stage !== currentStage) {
              currentStage = data.stage;
              stageCounter = 0;
              elements.loadingStatus.textContent = STAGE_MESSAGES[currentStage] || "Processing...";
              updatePipelineTracker(currentStage);
            } else {
              stageCounter++;
              if (stageCounter > 2) {
                elements.loadingStatus.textContent = FUN_MESSAGES[funMsgIdx % FUN_MESSAGES.length];
                funMsgIdx++;
              }
            }
          }
        } catch (e) {
            console.error(e);
        }
      };

      elements.loadingStatus.textContent = STAGE_MESSAGES[currentStage];
      const mInt = setInterval(pollStatus, 1500);

      const existingError = document.getElementById("errorPanel");
      if (existingError) existingError.style.display = "none";
      elements.initialState.style.display = "none";

      try {
        const token = sessionStorage.getItem("tm_token");
        const res = await fetch("/api/verify", {
          method: "POST",
          headers: { 
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token
          },
          body: JSON.stringify({ claim, request_id: requestId })
        });
        
        if (res.status === 401) {
          sessionStorage.removeItem("tm_token");
          window.location.reload();
          return;
        }
        if (!res.ok) {
          if (res.status === 503) {
            const errData = await res.json();
            showErrorPanel(
              errData.verdict_data?.one_line_verdict || 
              "The system is under heavy load. Please try again in a few minutes."
            );
            return;
          }
          throw new Error("Verification failed");
        }
        const data = await res.json();
        
        if (data.is_geopolitical === false) {
          elements.initialState.innerHTML = `
            <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="var(--danger)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom: 1.5rem;"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>
            <h2 style="font-size: 2rem; color: var(--danger); margin-bottom: 0.5rem;">Out of Scope</h2>
            <p style="font-size: 1.1rem; max-width: 600px; margin: 0 auto; color: var(--text-muted);">${data.rejection_reason}</p>
          `;
          elements.initialState.style.display = "block";
          elements.dashboard.style.display = "none";
          return;
        }

        renderDashboard(data);
        
      } catch (err) {
        showErrorPanel(err.message);
      } finally {
        elements.btnText.style.display = "block";
        elements.verifyLoader.style.display = "none";
        elements.verifyBtn.disabled = false;
        clearInterval(mInt);
        elements.loadingStatus.textContent = "";
        elements.loadingStatus.style.fontSize = '';
        elements.loadingStatus.style.opacity = '';
        elements.pipelineTracker.style.display = 'none';

        // Release wake lock — verification complete
        await releaseWakeLock();
      }
    }

    function renderDashboard(data) {
      document.getElementById('skeletonContainer').style.display = 'none';
      const rc = document.getElementById('resultsContainer');
      if (rc) rc.style.display = 'grid';
      // Check for infrastructure failure — show error panel, not dashboard
      const vdata = data.verdict_data || {};
      
      if (vdata.verdict === "TIMEOUT" || data.verdict === "TIMEOUT") {
          showErrorPanel(
              "The analysis timed out due to heavy load. " +
              "Please wait a few minutes and resubmit."
          );
          return;
      }
      
      if (vdata.verdict === "ANALYSIS_FAILED" || data.verdict === "ANALYSIS_FAILED") {
          showErrorPanel(
              "API capacity was temporarily exhausted. All available models " +
              "were rate-limited simultaneously. Please wait 2-3 minutes " +
              "and resubmit your claim."
          );
          return;   // Do not render the dashboard for infra failures
      }

      elements.initialState.style.display = "none";
      elements.dashboard.style.display = "grid";
      
      // Verdict Banner
      document.getElementById('verdictClaim').textContent = `"${data.original_claim || data.claim || ''}"`;
      elements.verdictValue.textContent = (vdata.verdict || data.verdict || "UNVERIFIABLE").replace(/_/g, " ");
      elements.verdictOneLine.textContent = vdata.one_line_verdict || "No clear verdict generated.";
      elements.confidenceBadge.textContent = `${vdata.confidence_label || 'Low'} Confidence`;
      
      const v = elements.verdictValue.textContent;
      let verdictColor, verdictGlow, badgeBg;

      if (v.includes("SUPPORTED") && !v.includes("PARTIALLY")) {
        verdictColor = "var(--success)";
        verdictGlow = "0 0 40px rgba(34, 197, 94, 0.1)";
        badgeBg = "var(--success-dim)";
        elements.verdictBanner.style.borderColor = "rgba(34, 197, 94, 0.3)";
      } else if (v.includes("PARTIALLY")) {
        verdictColor = "var(--warning)";
        verdictGlow = "0 0 40px rgba(234, 179, 8, 0.1)";
        badgeBg = "var(--warning-dim)";
        elements.verdictBanner.style.borderColor = "rgba(234, 179, 8, 0.3)";
      } else if (v.includes("CONTRADICTED")) {
        verdictColor = "var(--danger)";
        verdictGlow = "0 0 40px rgba(239, 68, 68, 0.1)";
        badgeBg = "var(--danger-dim)";
        elements.verdictBanner.style.borderColor = "rgba(239, 68, 68, 0.3)";
      } else {
        verdictColor = "var(--warning)";
        verdictGlow = "0 0 40px rgba(234, 179, 8, 0.08)";
        badgeBg = "var(--warning-dim)";
        elements.verdictBanner.style.borderColor = "rgba(234, 179, 8, 0.2)";
      }

      elements.verdictValue.style.color = verdictColor;
      elements.verdictBanner.style.boxShadow = verdictGlow;
      elements.confidenceBadge.style.background = badgeBg;
      elements.confidenceBadge.style.color = verdictColor;

      let verdictIcon = '◎';
      if (v.includes("SUPPORTED") && !v.includes("PARTIALLY")) {
        verdictIcon = '✓';
      } else if (v.includes("PARTIALLY")) {
        verdictIcon = '⊘';
      } else if (v.includes("CONTRADICTED")) {
        verdictIcon = '✕';
      }
      elements.verdictValue.innerHTML = `<span style="opacity: 0.7;">${verdictIcon}</span> ${elements.verdictValue.textContent}`;

      if (data._from_cache) {
          elements.verdictBanner.insertAdjacentHTML('beforeend',
              '<div style="font-size:0.75rem; color: var(--text-muted); ' +
              'margin-top: 0.5rem; opacity: 0.6;">⚡ Retrieved from cache</div>'
          );
      }

      // Breakdown
      elements.fullReasoning.textContent = vdata.full_reasoning || "No reasoning provided.";
      elements.whatIsTrue.textContent = vdata.what_is_true || "N/A";
      elements.whatIsFalse.textContent = vdata.what_is_false || "N/A";
      elements.whatIsUnclear.textContent = vdata.what_is_unclear || "N/A";

      // Perspectives
      elements.blocGrid.innerHTML = "";
      if (data.perspective_groups && Array.isArray(data.perspective_groups)) {
        data.perspective_groups.forEach(pg => {
          // The user specifically requested to keep names plain without flags.
          const label = pg.group_label || "Unknown Bloc";
          const stance = pg.collective_stance || "Unknown";
          const narrative = pg.collective_narrative || "No narrative available.";
          
          // FIXED: One pill per category, no comma-splitting
          const emphasizeText = (pg.what_they_emphasize || "N/A").trim();
          const emphasizeTags = `<span class="pill-tag emphasize">${emphasizeText}</span>`;
            
          const omitText = (pg.what_they_omit || "N/A").trim();
          const omitTags = `<span class="pill-tag omit">${omitText}</span>`;
          
          // Color-code stance badge
          let stanceBg, stanceColor;
          const stanceUpper = stance.toUpperCase();
          if (stanceUpper.includes("SUPPORT") && !stanceUpper.includes("PARTIALLY")) {
            stanceBg = "var(--success-dim)"; stanceColor = "var(--success)";
          } else if (stanceUpper.includes("CONTRADICT")) {
            stanceBg = "var(--danger-dim)"; stanceColor = "var(--danger)";
          } else if (stanceUpper.includes("PARTIALLY")) {
            stanceBg = "var(--warning-dim)"; stanceColor = "var(--warning)";
          } else {
            stanceBg = "rgba(255,255,255,0.08)"; stanceColor = "var(--text-muted)";
          }
          
          elements.blocGrid.innerHTML += `
            <div class="bloc-card">
              <div class="bloc-card-header">
                <h4 class="bloc-title">${label}</h4>
                <span class="bloc-stance" style="background: ${stanceBg}; color: ${stanceColor};">${stance}</span>
              </div>
              <div class="bloc-content">
                <p style="margin: 0 0 1.25rem 0; font-size: 0.95rem; color: var(--text-muted); line-height: 1.7;">${narrative}</p>
                <div style="margin-top: auto; display: flex; flex-direction: column; gap: 1rem;">
                  <div>
                    <strong style="font-size: 0.75rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-dim); display: block; margin-bottom: 0.5rem;">EMPHASIZES</strong>
                    <div class="tag-container">${emphasizeTags}</div>
                  </div>
                  <div>
                    <strong style="font-size: 0.75rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-dim); display: block; margin-bottom: 0.5rem;">OMITS</strong>
                    <div class="tag-container">${omitTags}</div>
                  </div>
                </div>
              </div>
            </div>
          `;
        });
      }

      // Hidden Stories
      elements.hiddenStoriesContainer.innerHTML = "";
      document.getElementById('hiddenStoriesCount').textContent = Array.isArray(data.hidden_stories) ? data.hidden_stories.length : 0;
      
      if (data.hidden_stories && Array.isArray(data.hidden_stories) && data.hidden_stories.length > 0) {
        data.hidden_stories.forEach(hs => {
          const title = hs.title || "Untitled Story";
          const explanation = hs.explanation || "No explanation available.";
          const significance = hs.significance || "Unknown significance.";
          const hintSources = Array.isArray(hs.which_sources_hint_at_this)
            ? hs.which_sources_hint_at_this.map(s => `<div style="margin-bottom: 0.25rem;">${s}</div>`).join("")
            : "None identified";
          const suppressSources = Array.isArray(hs.which_sources_suppress_this)
            ? hs.which_sources_suppress_this.map(s => `<div style="margin-bottom: 0.25rem;">${s}</div>`).join("")
            : "None identified";
          
          elements.hiddenStoriesContainer.innerHTML += `
            <div class="accordion-item">
              <div class="accordion-header" onclick="toggleAccordion(this)">
                <span>
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:0.5rem; vertical-align: middle;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>
                  ${title}
                </span>
                <svg class="chevron-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
              </div>
              <div class="accordion-content">
                <p style="margin-top: 1rem;">${explanation}</p>
                <div class="why-it-matters">
                  <div class="why-it-matters-label">WHY IT MATTERS</div>
                  <p>${significance}</p>
                </div>
                <div class="hidden-story-sources" style="display: flex; gap: 3rem; font-size: 0.9rem; margin-top: 1.5rem; border-top: 1px solid var(--panel-border); padding-top: 1.5rem;">
                  <div style="flex: 1;">
                    <strong style="font-size: 0.75rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-main); display: block; margin-bottom: 0.75rem;">SOURCES HINTING AT THIS</strong>
                    <div style="color: var(--text-muted);">${hintSources}</div>
                  </div>
                  <div style="flex: 1;">
                    <strong style="font-size: 0.75rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-main); display: block; margin-bottom: 0.75rem;">SOURCES SUPPRESSING THIS</strong>
                    <div style="color: var(--text-muted);">${suppressSources}</div>
                  </div>
                </div>
              </div>
            </div>
          `;
        });
      } else {
        elements.hiddenStoriesContainer.innerHTML = "<p style='color: var(--text-muted);'>No hidden narratives extracted.</p>";
      }

      // Sources Table
      // ── Split sources into two groups ────────────────────────────────
      const RELEVANT_STANCES = new Set(["SUPPORTS", "CONTRADICTS", "PARTIALLY_SUPPORTS"]);
      const relevantSources = (data.source_analyses || []).filter(
          sa => RELEVANT_STANCES.has(sa.stance)
      );
      const backgroundSources = (data.source_analyses || []).filter(
          sa => !RELEVANT_STANCES.has(sa.stance)
      );

      // ── Update counts in panel header ────────────────────────────────
      document.getElementById("totalCount").textContent =
          (data.source_analyses || []).length;
      document.getElementById("backgroundCount").textContent =
          backgroundSources.length;

      // ── Low-evidence warning ──────────────────────────────────────────
      const warningEl = document.getElementById("lowEvidenceWarning");
      if (relevantSources.length === 0) {
          warningEl.innerHTML = "⚠️ <strong>Limited direct evidence</strong><br>No sources were found which confirm or deny this claim.";
          warningEl.style.display = "block";
      } else if (relevantSources.length < 3) {
          warningEl.innerHTML = "⚠️ <strong>Limited direct evidence</strong><br>Very Few sources were found which directly confirm or deny this claim.";
          warningEl.style.display = "block";
      } else {
          warningEl.style.display = "none";
      }

      // ── Render relevant sources table ─────────────────────────────────
      const relevantBody = document.getElementById("relevantSourcesBody");
      relevantBody.innerHTML = "";
      const noRelevantMsg = document.getElementById("noRelevantMsg");

      if (relevantSources.length === 0) {
          noRelevantMsg.style.display = "block";
      } else {
          noRelevantMsg.style.display = "none";
          relevantSources.forEach(sa => {
              relevantBody.innerHTML += buildSourceRow(sa);
          });
      }

      // ── Render background sources table ───────────────────────────────
      const backgroundBody = document.getElementById("backgroundSourcesBody");
      backgroundBody.innerHTML = "";
      backgroundSources.forEach(sa => {
          backgroundBody.innerHTML += buildSourceRow(sa);
      });

      // ── Hide background accordion entirely if nothing to show ─────────
      const bgSection = document.getElementById("backgroundSourcesSection");
      bgSection.style.display = backgroundSources.length > 0 ? "block" : "none";
    }
  