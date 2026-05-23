document.addEventListener('DOMContentLoaded', () => {
    
    // ================= STATE MANAGEMENT =================
    let currentStep = 1;
    const totalSteps = 4;
    let userProfile = {
        budget: 1600,
        needs_transit: true,
        lifestyle: 'space',
        borough: 'all'
    };
    let matchedListings = [];

    // ================= DOM ELEMENT REFERENCES =================
    // Screens
    const landingScreen = document.getElementById('landing-screen');
    const wizardScreen = document.getElementById('wizard-screen');
    const loadingScreen = document.getElementById('loading-screen');
    const dashboardScreen = document.getElementById('dashboard-screen');

    // Controls
    const startBtn = document.getElementById('start-consultation-btn');
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    const resetWizardBtn = document.getElementById('reset-wizard-btn');

    // Progress Indicators
    const progressBar = document.getElementById('wizard-progress');
    const currentStepNum = document.getElementById('current-step-num');

    // Step Elements
    const steps = document.querySelectorAll('.wizard-step');
    const budgetRange = document.getElementById('budget-range');
    const budgetVal = document.getElementById('budget-val');
    const appModeBadge = document.getElementById('app-mode-badge');

    // Dashboard Elements
    const conciergeReportContent = document.getElementById('concierge-report-content');
    const resultsCount = document.getElementById('results-count');
    const listingsCardsContainer = document.getElementById('listings-cards-container');

    // Modal Elements
    const scoreModal = document.getElementById('score-breakdown-modal');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const modalAptAddress = document.getElementById('modal-apt-address');
    const modalAptScore = document.getElementById('modal-apt-score');

    // ================= EVENT BINDINGS =================

    // Start Consultation
    startBtn.addEventListener('click', () => {
        transitionScreen(landingScreen, wizardScreen);
        updateWizardUI();
    });

    // Wizard Back Button
    prevBtn.addEventListener('click', () => {
        if (currentStep > 1) {
            currentStep--;
            updateWizardUI();
        }
    });

    // Wizard Next / Submit Button
    nextBtn.addEventListener('click', () => {
        if (validateStep(currentStep)) {
            saveStepData(currentStep);
            if (currentStep < totalSteps) {
                currentStep++;
                updateWizardUI();
            } else {
                submitConsultation();
            }
        }
    });

    // Reset Consultation
    resetWizardBtn.addEventListener('click', () => {
        currentStep = 1;
        budgetRange.value = 1600;
        budgetVal.textContent = '1600';
        resetWizardBtn.style.display = 'none';
        transitionScreen(dashboardScreen, wizardScreen);
        updateWizardUI();
    });

    // Budget Slider Input Event
    budgetRange.addEventListener('input', (e) => {
        budgetVal.textContent = e.target.value;
    });

    // Modal Close
    closeModalBtn.addEventListener('click', () => {
        scoreModal.classList.remove('active-modal');
    });
    window.addEventListener('click', (e) => {
        if (e.target === scoreModal) {
            scoreModal.classList.remove('active-modal');
        }
    });

    // ================= WIZARD NAVIGATION LOGIC =================

    function transitionScreen(fromScreen, toScreen) {
        fromScreen.classList.remove('active-screen');
        fromScreen.classList.add('hidden-screen');
        toScreen.classList.remove('hidden-screen');
        toScreen.classList.add('active-screen');
    }

    function updateWizardUI() {
        // Update steps view
        steps.forEach(step => {
            step.classList.remove('active-step');
            if (parseInt(step.dataset.step) === currentStep) {
                step.classList.add('active-step');
            }
        });

        // Update progress indicators
        const progressPercent = (currentStep / totalSteps) * 100;
        progressBar.style.width = `${progressPercent}%`;
        currentStepNum.textContent = currentStep;

        // Button States
        if (currentStep === 1) {
            prevBtn.disabled = true;
            prevBtn.classList.add('disabled-btn');
        } else {
            prevBtn.disabled = false;
            prevBtn.classList.remove('disabled-btn');
        }

        if (currentStep === totalSteps) {
            nextBtn.innerHTML = `Analyze Listings <i class="fa-solid fa-compass icon-right"></i>`;
        } else {
            nextBtn.innerHTML = `Next <i class="fa-solid fa-arrow-right icon-right"></i>`;
        }
    }

    function validateStep(_step) {
        return true;
    }

    function saveStepData(step) {
        switch (step) {
            case 1:
                userProfile.budget = parseFloat(budgetRange.value);
                break;
            case 2:
                userProfile.needs_transit = document.querySelector('input[name="transit-pref"]:checked').value === 'yes';
                break;
            case 3:
                userProfile.lifestyle = document.querySelector('input[name="lifestyle-pref"]:checked').value;
                break;
            case 4:
                userProfile.borough = document.querySelector('input[name="borough-pref"]:checked').value;
                break;
        }
    }

    // ================= SUBMIT & LOADING SEQUENCE =================

    function submitConsultation() {
        // Transition to loader screen
        transitionScreen(wizardScreen, loadingScreen);

        // Reset step animations
        const step1 = document.getElementById('loading-step-1');
        const step2 = document.getElementById('loading-step-2');
        const step3 = document.getElementById('loading-step-3');
        const step4 = document.getElementById('loading-step-4');

        step1.className = 'loading-step active-loading-step';
        step2.className = 'loading-step';
        step3.className = 'loading-step';
        step4.className = 'loading-step';

        appModeBadge.innerHTML = `<span class="dot pulse-emerald"></span> ClickHouse Dataset Active`;
        appModeBadge.className = 'mode-badge';

        // Timing sequences for immersive loaded stages
        setTimeout(() => {
            step1.className = 'loading-step completed-loading-step';
            step2.className = 'loading-step active-loading-step';
        }, 1500);

        setTimeout(() => {
            step2.className = 'loading-step completed-loading-step';
            step3.className = 'loading-step active-loading-step';
        }, 3000);

        setTimeout(() => {
            step3.className = 'loading-step completed-loading-step';
            step4.className = 'loading-step active-loading-step';
        }, 4500);

        // Fetch data from FastAPI backend
        fetch('/api/match', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(userProfile)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error("Matchmaker server returned an error.");
            }
            return response.json();
        })
        .then(data => {
            setTimeout(() => {
                step4.className = 'loading-step completed-loading-step';
                
                // Load matches and transition to dashboard
                matchedListings = data.matches || [];
                renderDashboard(data);
                
                resetWizardBtn.style.display = 'inline-flex';
                transitionScreen(loadingScreen, dashboardScreen);
            }, 6000);
        })
        .catch(error => {
            console.error("Consultation fetch failed:", error);
            setTimeout(() => {
                alert("We couldn't reach the housing match engine. Aura will fall back to offline match templates.");
                // Fake matches to show application completeness if server is offline
                renderOfflineFallback();
                resetWizardBtn.style.display = 'inline-flex';
                transitionScreen(loadingScreen, dashboardScreen);
            }, 6000);
        });
    }

    // ================= DASHBOARD RENDERING =================

    function renderDashboard(data) {
        // 1. Render Count Badge
        resultsCount.textContent = data.total_results || 0;

        // 2. Render AI report sidebar
        const htmlReport = parseMarkdownToHtml(data.concierge_report);
        conciergeReportContent.innerHTML = htmlReport;

        // 3. Render Card Grid
        listingsCardsContainer.innerHTML = '';
        if (matchedListings.length === 0) {
            listingsCardsContainer.innerHTML = `
                <div class="glass-panel text-center" style="grid-column: span 2; padding: 40px;">
                    <h3>No listings found in budget.</h3>
                    <p style="color: var(--text-muted)">Consider increasing your budget slider or expanding borough options.</p>
                </div>
            `;
            return;
        }

        matchedListings.forEach((listing, index) => {
            const card = document.createElement('div');
            card.className = 'listing-card';

            const scoreClass = listing.overall_score >= 85 ? '' : 'medium-match';

            card.innerHTML = `
                <div class="card-header-meta">
                    <div class="match-meter ${scoreClass}">${listing.overall_score}% Match</div>
                    <div class="listing-price">$${listing.price_per_month}<span style="font-size: 14px; font-weight: 500; color: var(--text-muted)">/mo</span></div>
                </div>
                <div>
                    <h4 class="listing-address">${listing.address}</h4>
                    <div class="listing-borough-label">
                        <i class="fa-solid fa-map-pin"></i> ${listing.borough_name}
                    </div>
                </div>
                <div class="listing-features-tags">
                    <span class="tag-sm"><i class="fa-solid fa-bed"></i> ${listing.beds || '1'} Bed</span>
                    <span class="tag-sm"><i class="fa-solid fa-bath"></i> ${listing.baths || '1'} Bath</span>
                    ${listing.sqft ? `<span class="tag-sm"><i class="fa-solid fa-ruler-combined"></i> ${listing.sqft} sqft</span>` : ''}
                </div>
                <div class="listing-card-footer">
                    <button class="btn btn-secondary btn-sm match-breakdown-btn" data-index="${index}">
                        <i class="fa-solid fa-chart-bar"></i> Why this match?
                    </button>
                    <a href="${listing.link}" target="_blank" class="btn btn-primary btn-sm" style="text-decoration: none;">
                        View Zillow <i class="fa-solid fa-arrow-up-right-from-square icon-right"></i>
                    </a>
                </div>
            `;
            listingsCardsContainer.appendChild(card);
        });

        // Add event listeners to Modal buttons
        document.querySelectorAll('.match-breakdown-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(btn.dataset.index);
                openScoreModal(matchedListings[idx]);
            });
        });
    }

    // Modal scoring detail rendering
    function openScoreModal(listing) {
        modalAptAddress.textContent = listing.address;
        modalAptScore.textContent = `${listing.overall_score}%`;

        // Progress bar updates
        const sets = ['budget', 'borough', 'transit', 'lifestyle'];
        sets.forEach(key => {
            const scoreVal = listing.breakdown[key] || 0;
            document.getElementById(`score-val-${key}`).textContent = `${scoreVal}%`;
            
            const bar = document.getElementById(`score-bar-${key}`);
            bar.style.width = `${scoreVal}%`;

            // Adjust bar colors dynamically if too low
            if (scoreVal < 40) {
                bar.style.backgroundColor = 'var(--accent-coral)';
            } else if (scoreVal < 70) {
                bar.style.backgroundColor = 'var(--accent-gold)';
            } else if (key === 'budget') {
                bar.style.backgroundColor = 'var(--accent-emerald)';
            } else {
                bar.style.backgroundColor = ''; // Restore default css var class coloring
            }
        });

        document.getElementById('score-detail-lifestyle').textContent = listing.lifestyle_details || 'Standard lifestyle priority scoring mapping.';

        scoreModal.classList.add('active-modal');
    }

    // Offline / Network Failure Fallback Template Generator
    function renderOfflineFallback() {
        const fakeData = {
            total_results: 1,
            concierge_report: `### 🗽 Offline Mode Active
We could not reach the server, but Aura has generated a local concierge preview for you!

- **Budget ceiling**: Fits within your limits.
- **Commute strategy**: Positioned along direct train hubs straight to your work at **${userProfile.work_location}**.
- **Outer Borough Value**: Highly accessible.`,
            matches: [
                {
                    address: "Trylon Tower | 98-81 Queens Blvd, Rego Park, NY",
                    price_per_month: 2000,
                    beds: 1,
                    baths: 1,
                    sqft: 750,
                    link: "https://www.zillow.com",
                    is_elevator: true,
                    is_pet_friendly: true,
                    overall_score: 94.5,
                    borough_name: "Queens",
                    lifestyle_details: "Spacious High-Rise apartment situated directly adjacent to transit corridor.",
                    breakdown: {
                        budget: 100,
                        borough: 100,
                        transit: 95,
                        lifestyle: 90,
                        pet: 100,
                        elevator: 100
                    }
                }
            ]
        };
        matchedListings = fakeData.matches;
        renderDashboard(fakeData);
    }

    // ================= MULTI-LINE SIMPLE MARKDOWN PARSER =================
    function parseMarkdownToHtml(mdText) {
        if (!mdText) return '';
        let html = mdText;
        
        // Escape standard HTML symbols
        html = html.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

        // Headers
        html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
        html = html.replace(/^#### (.*$)/gim, '<h4>$1</h4>');
        
        // Bold
        html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
        
        // Horizontal rule
        html = html.replace(/^---$/gim, '<hr>');

        // Unordered Bullet points
        html = html.replace(/^\- (.*$)/gim, '<li>$1</li>');
        
        // Wrap adjacent li elements into ul (basic parsing logic)
        html = html.replace(/(<li>.*<\/li>)/gms, '<ul>$1</ul>');

        return html;
    }
});
