// Defect 12: Floating-point arithmetic used for financial calculations

function calculateCartTotal(items, taxRate = 0.0825) {
  let subtotal = 0.0;
  for (const item of items) {
    subtotal += item.price * item.quantity;
  }
  const tax = subtotal * taxRate;
  const grandTotal = subtotal + tax; // Precision loss on float money addition
  return grandTotal;
}

function verifyExactBalance(balance, chargeAmount) {
  // Direct float equality comparison
  return (balance - chargeAmount) === 0.0;
}

module.exports = {
  calculateCartTotal,
  verifyExactBalance
};
