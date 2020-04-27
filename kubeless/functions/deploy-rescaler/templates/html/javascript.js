"use strict";
window.addEventListener("load", function () {
    function sendData() {
        var path = "/"

        const XHR = new XMLHttpRequest();

        // Bind the FormData object and the form element
        const FD = new FormData(form);

        // Define what happens on successful data submission
        XHR.addEventListener("load", function (event) {
            document.getElementById('output').innerHTML = event.target.responseText;
            console.info(event.target.responseText);
        });

        // Define what happens in case of error
        XHR.addEventListener("error", function (event) {
            alert("Oops! Something went wrong.");
        });

        // Set up our request
        XHR.open("POST", path);

        XHR.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        var json = {};
        for (const [key, value] of FD.entries()) {
            json[key] = value;
        }
        var json = JSON.stringify(json);
        console.info(json);

        // The data sent is what the user provided in the form
        XHR.send(json);
    }

    // Access the form element...
    var form = document.getElementById("rescaler");

    // ...and take over its submit event.
    form.addEventListener("submit", function (event) {
        event.preventDefault();

        sendData();
    });
});