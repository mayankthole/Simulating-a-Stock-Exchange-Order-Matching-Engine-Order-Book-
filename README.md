<img width="1214" height="845" alt="Screenshot 2025-10-31 at 1 06 18 AM" src="https://github.com/user-attachments/assets/5425880d-3ffb-44fc-b514-c3353df4d1a7" />
pygame>=2.5.2
tzdata>=2025.2rice‑time priority:
  - Match at best opposite price first
  - Within a price, fill oldest order first (FIFO by OID)
  - Large takers may fill multiple orders/levels (partial fills logged separately)
- LTP updates to the price of the last trade in each match sequence

## Controls
- Order Entry: toggle LIMIT/MARKET and Buy/Sell; use +/- to set price/qty; click “Place Order”
- Sample Book: populates a rich book and auto‑runs short demo trades
- Reset: clears book, logs, counters, and LTP back to 1000
- Run Demo (15 steps): plays random actions step‑by‑step (1s pauses) to visualize matching
- Bottom tabs: Executed, Pending, All Orders Punched, Trade Logs; use mouse wheel to scroll

## Output Files
- `executed_trades.csv`: timestamp, price, qty, taker, counterparty, resting side, OID, TID
- `events_log.csv`: timestamp, event (submit/result/trade), actor, IDs, side, type, price, qty, filled, status, note

## Screenshots (add your images)
- docs/screenshot-orderbook.png
- docs/screenshot-executed.png
- docs/screenshot-demo.png

## Notes
- Price band: 990–1010 (tick=1)
- Brokerage: applied to player orders only when any quantity is filled (partial or full)

## License
MIT
