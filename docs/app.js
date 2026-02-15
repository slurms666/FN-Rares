const grid = document.getElementById("grid");
const updatedText = document.getElementById("updated");

// Configuration
const DATA_URL = "./data/top.json";
const ITEM_LINK_BASE = "https://fnbr.co/cosmetics?id=";


// ---------------------
// Helpers
// ---------------------

function formatDays(days) {
    if (days === null || days === undefined) return "Unknown";

    if (days >= 365) {
        const years = Math.floor(days / 365);
        return `${years}y ${days % 365}d ago`;
    }

    if (days >= 30) {
        const months = Math.floor(days / 30);
        return `${months}m ${days % 30}d ago`;
    }

    return `${days} days ago`;
}

function createCard(item) {
    const card = document.createElement("div");
    card.className = "card";

    const id = item.id || "";
    const name = item.name || "Unknown";
    const icon = item.icon || "";
    const days = item.days_since;

    const link = ITEM_LINK_BASE + encodeURIComponent(id);

    card.innerHTML = `
        <a href="${link}" target="_blank" rel="noopener">
            <img src="${icon}" alt="${name}" loading="lazy">
        </a>
        <div class="name">${name}</div>
        <div class="days">${formatDays(days)}</div>
    `;

    return card;
}

function showError(message) {
    updatedText.textContent = message;
    console.error(message);
}


// ---------------------
// Main loader
// ---------------------

async function loadData() {
    try {
        const response = await fetch(DATA_URL, { cache: "no-store" });

        if (!response.ok) {
            showError("Failed to load data");
            return;
        }

        const data = await response.json();

        const items = data.items || [];

        if (items.length === 0) {
            showError("No items in shop right now");
            return;
        }

        // Clear grid
        grid.innerHTML = "";

        // Render cards
        items.forEach(item => {
            const card = createCard(item);
            grid.appendChild(card);
        });

        // Update timestamp
        if (data.updated_utc) {
            const date = new Date(data.updated_utc);
            updatedText.textContent =
                "Updated: " + date.toLocaleString();
        } else {
            updatedText.textContent = "";
        }

    } catch (err) {
        showError("Error loading data");
        console.error(err);
    }
}


// Run
loadData();
