const grid = document.getElementById("grid");
const updatedText = document.getElementById("updated");

// Load top rare items
fetch("./data/top.json")
    .then(res => res.json())
    .then(data => {
        const items = data.items;

        items.forEach(item => {
            const card = document.createElement("div");
            card.className = "card";

            card.innerHTML = `
                <img src="${item.icon}" alt="${item.name}">
                <div class="name">${item.name}</div>
                <div class="days">${item.days_since} days ago</div>
            `;

            grid.appendChild(card);
        });

        // Show update time
        const date = new Date(data.updated_utc);
        updatedText.textContent =
            "Updated: " + date.toLocaleString();
    })
    .catch(err => {
        updatedText.textContent = "Failed to load data";
        console.error(err);
    });
