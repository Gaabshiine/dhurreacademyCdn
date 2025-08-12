"use strict";


const multiRange = document.querySelectorAll(".multi-range");

if (multiRange.length) {
  let minDollars = 0;
  let maxDollars = 500;

  let minSlider = document.querySelector("#min");
  let maxSlider = document.querySelector("#max");

  function numberWithSpaces(number) {
    return number.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  }

  function updateDollars() {
    let fromValue =
      ((maxDollars - minDollars) * minSlider.value) / 100 + minDollars;
    let toValue =
      ((maxDollars - minDollars) * maxSlider.value) / 100 + minDollars;

    document.querySelector("#from").textContent = `$${numberWithSpaces(
      Math.floor(fromValue)
    )}`;
    document.querySelector("#to").textContent = `$${numberWithSpaces(
      Math.floor(toValue)
    )}`;
  }

  maxSlider.addEventListener("input", () => {
    let minValue = parseInt(minSlider.value);
    let maxValue = parseInt(maxSlider.value);

    if (maxValue < minValue + 10) {
      minSlider.value = maxValue - 10;

      if (minValue === parseInt(minSlider.min)) {
        maxSlider.value = 10;
      }
    }

    updateDollars();
  });

  minSlider.addEventListener("input", () => {
    let minValue = parseInt(minSlider.value);
    let maxValue = parseInt(maxSlider.value);

    if (minValue > maxValue - 10) {
      maxSlider.value = minValue + 10;

      if (maxValue === parseInt(maxSlider.max)) {
        minSlider.value = parseInt(maxSlider.max) - 10;
      }
    }

    updateDollars();
  });
}
    

