document.addEventListener(
    "DOMContentLoaded",
    () => {

        const form =
            document.getElementById(
                "comicForm"
            );

        const button =
            document.getElementById(
                "generateButton"
            );

        if (!form || !button) {
            return;
        }


        form.addEventListener(
            "submit",
            () => {

                button.disabled = true;

                button.innerHTML =
                    `
                    <span>
                        ✨ Creating Your Comic...
                    </span>
                    `;

                button.style.opacity = "0.7";

            }
        );

    }
);