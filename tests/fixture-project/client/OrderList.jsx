import React, { useState, useEffect } from "react";

export default function OrderList({ userId, filterStatus }) {
  const [orders, setOrders] = useState([]);
  const [refreshCount, setRefreshCount] = useState(0);

  // Defect 9: Stale React closure and missing dependencies
  useEffect(() => {
    const timer = setInterval(() => {
      // Reads stale refreshCount and filterStatus due to empty dependency array
      setRefreshCount(refreshCount + 1);
      fetch(`/api/orders?status=${filterStatus}&user=${userId}`)
        .then((res) => res.json())
        .then((data) => setOrders(data));
    }, 5000);

    return () => clearInterval(timer);
  }, []);

  // Decoy 3: Math.random used solely for UI visual shuffling
  const displayedOrders = [...orders].sort(() => Math.random() - 0.5);

  return (
    <div className="order-list">
      <h2>Your Orders (Refreshed: {refreshCount})</h2>
      <ul>
        {displayedOrders.map((order) => (
          <li key={order._id}>
            Order #{order._id} - ${order.totalAmount} ({order.status})
          </li>
        ))}
      </ul>
    </div>
  );
}
