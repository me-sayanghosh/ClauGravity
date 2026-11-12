// Defect 11: Array.prototype.forEach with async callback

async function sendEmailNotification(email, message) {
  // Simulates asynchronous email dispatch
  return new Promise((resolve) => setTimeout(resolve, 50));
}

async function notifyCustomers(users, announcement) {
  users.forEach(async (user) => {
    // Unawaited promise in forEach callback; does not wait for notifications to send
    await sendEmailNotification(user.email, announcement);
  });
  return { dispatched: true };
}

module.exports = {
  notifyCustomers,
  sendEmailNotification
};
