const express = require("express");
const { requireAuth } = require("../middleware/auth");

const router = express.Router();

async function fakeStripeCharge(cardToken, amount) {
  if (amount <= 0 || !cardToken) {
    throw new Error("Invalid payment parameters");
  }
  return { id: "ch_test_123", status: "succeeded" };
}

// Defect 10: Swallowed payment error in empty catch block
router.post("/charge", requireAuth, async (req, res) => {
  const { cardToken, amount } = req.body;
  let chargeResult = null;

  try {
    chargeResult = await fakeStripeCharge(cardToken, amount);
  } catch (err) {
    // Defect: empty catch silently swallows payment failure!
  }

  res.json({
    status: "success",
    charge: chargeResult
  });
});

module.exports = router;
