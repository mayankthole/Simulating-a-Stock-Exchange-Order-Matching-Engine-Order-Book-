import pygame
import sys
import random
import os
import csv
from datetime import datetime
from zoneinfo import ZoneInfo

pygame.init()

WIDTH, HEIGHT = 1230, 850

FPS = 30
BG_COLOR = (255, 255, 255)
font = pygame.font.SysFont(None, 24)
BIGFONT = pygame.font.SysFont(None, 30)

PRICE_MIN, PRICE_MAX = 990, 1010
PRICE_TICK = 1  # price step size
LTP = 1000  # For reference display


# --- Animation Settings ---
ANIM_STEP_PER_FRAME = 2  # qty units per frame for bar growth/shrink
FLASH_FRAMES = 18        # frames to flash a price level after a trade

# --- Order ID counter ---
ORDER_ID_COUNTER = 1
TAKER_ID_COUNTER = 1

# --- Core Order Book Logic ---
def new_order_book():
    return {"bids": [], "asks": []}


def make_background_surface(width, height):
    # Create a soft vertical gradient background once
    surf = pygame.Surface((width, height))
    top_col = (242, 246, 255)
    bot_col = (252, 254, 255)
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(top_col[0] + (bot_col[0] - top_col[0]) * t)
        g = int(top_col[1] + (bot_col[1] - top_col[1]) * t)
        b = int(top_col[2] + (bot_col[2] - top_col[2]) * t)
        pygame.draw.line(surf, (r, g, b), (0, y), (width, y))
    return surf


def sort_book(book):
    book["bids"].sort(key=lambda x: -x[0])
    book["asks"].sort(key=lambda x: x[0])


def place_limit_order(order_book, side, price, qty, is_player, taker_id=None):
    global ORDER_ID_COUNTER
    trades = []
    fifo_entries = []
    if side == "buy":
        while qty > 0 and order_book["asks"] and price >= order_book["asks"][0][0]:
            ask_price, ask_qty, ask_player, ask_oid = order_book["asks"][0]
            traded = min(qty, ask_qty)
            trades.append((ask_price, traded, 'You' if is_player else 'Bot', 'Seller' if ask_player else 'Bot', ask_oid, taker_id))
            fifo_entries.append((ask_oid, 'Ask', ask_price, traded, 'You' if is_player else 'Bot', taker_id))
            qty -= traded
            ask_qty -= traded
            if ask_qty == 0:
                order_book["asks"].pop(0)
            else:
                order_book["asks"][0] = (ask_price, ask_qty, ask_player, ask_oid)
        if qty > 0:
            order_book["bids"].append((price, qty, is_player, ORDER_ID_COUNTER))
            ORDER_ID_COUNTER += 1
            sort_book(order_book)
    else:
        while qty > 0 and order_book["bids"] and price <= order_book["bids"][0][0]:
            bid_price, bid_qty, bid_player, bid_oid = order_book["bids"][0]
            traded = min(qty, bid_qty)
            trades.append((bid_price, traded, 'You' if is_player else 'Bot', 'Buyer' if bid_player else 'Bot', bid_oid, taker_id))
            fifo_entries.append((bid_oid, 'Bid', bid_price, traded, 'You' if is_player else 'Bot', taker_id))
            qty -= traded
            bid_qty -= traded
            if bid_qty == 0:
                order_book["bids"].pop(0)
            else:
                order_book["bids"][0] = (bid_price, bid_qty, bid_player, bid_oid)
        if qty > 0:
            order_book["asks"].append((price, qty, is_player, ORDER_ID_COUNTER))
            ORDER_ID_COUNTER += 1
            sort_book(order_book)
    return trades, fifo_entries


def place_market_order(order_book, side, qty, is_player, taker_id=None):
    trades = []
    fifo_entries = []
    if side == "buy":
        while qty > 0 and order_book["asks"]:
            ask_price, ask_qty, ask_player, ask_oid = order_book["asks"][0]
            traded = min(qty, ask_qty)
            trades.append((ask_price, traded, 'You' if is_player else 'Bot', 'Seller' if ask_player else 'Bot', ask_oid, taker_id))
            fifo_entries.append((ask_oid, 'Ask', ask_price, traded, 'You' if is_player else 'Bot', taker_id))
            qty -= traded
            ask_qty -= traded
            if ask_qty == 0:
                order_book["asks"].pop(0)
            else:
                order_book["asks"][0] = (ask_price, ask_qty, ask_player, ask_oid)
    else:
        while qty > 0 and order_book["bids"]:
            bid_price, bid_qty, bid_player, bid_oid = order_book["bids"][0]
            traded = min(qty, bid_qty)
            trades.append((bid_price, traded, 'You' if is_player else 'Bot', 'Buyer' if bid_player else 'Bot', bid_oid, taker_id))
            fifo_entries.append((bid_oid, 'Bid', bid_price, traded, 'You' if is_player else 'Bot', taker_id))
            qty -= traded
            bid_qty -= traded
            if bid_qty == 0:
                order_book["bids"].pop(0)
            else:
                order_book["bids"][0] = (bid_price, bid_qty, bid_player, bid_oid)
    return trades, fifo_entries


def draw_orderbook(screen, order_book, display_bids, display_asks, flash_bids, flash_asks):
    top, bot = 70, HEIGHT - 260
    px2y = lambda px: int(top + (1010 - px) // 1 * ((bot - top) / (1010 - 990 + 1)))

    # Light background bands for bid and ask columns (closer together)
    # Limit vertical extent strictly to the plotted grid (stop at 990 level)
    y_bottom_grid = px2y(990)
    band_height = max(0, y_bottom_grid - top)
    # Bids area: x 200 -> 520 (bars grow left from 520)
    pygame.draw.rect(screen, (232, 246, 238), (200, top, 520 - 200, band_height))  # light green tint
    # Asks area: x 550 -> 880 (bars grow right from 550)
    pygame.draw.rect(screen, (250, 235, 235), (550, top, 880 - 550, band_height))  # light red tint

    for px in range(1010, 990 - 1, -1):
        y = px2y(px)
        pygame.draw.line(screen, (230, 230, 230), (200, y), (880, y), 1)
        screen.blit(font.render(f"{px}", 1, (100, 100, 130)), (160, y - 10))

    # Draw aggregated bid bars with animation and flash
    for px in sorted(display_bids.keys(), reverse=True):
        qty = display_bids[px]
        if qty <= 0:
            continue
        y = px2y(px)
        base_col = (0, 180, 0)
        if flash_bids.get(px, 0) > 0:
            t = flash_bids[px]
            boost = min(75, 20 + t * 3)
            col = (min(255, base_col[0] + boost), min(255, base_col[1] + boost), min(255, base_col[2] + boost))
        else:
            col = base_col
        max_w_bid = 520 - 200
        w = min(int(qty) * 3, max_w_bid)
        pygame.draw.rect(screen, col, (520 - w, y - 10, w, 18), border_radius=3)
        qty_text = font.render(str(int(qty)), True, (255, 255, 255))
        text_x = max(200, 520 - w + 4)
        screen.blit(qty_text, (text_x, y - 9))

    # Draw aggregated ask bars with animation and flash
    for px in sorted(display_asks.keys()):
        qty = display_asks[px]
        if qty <= 0:
            continue
        y = px2y(px)
        base_col = (210, 40, 40)
        if flash_asks.get(px, 0) > 0:
            t = flash_asks[px]
            boost = min(75, 20 + t * 3)
            col = (min(255, base_col[0] + boost), min(255, base_col[1] + boost), min(255, base_col[2] + boost))
        else:
            col = base_col
        max_w_ask = 880 - 550
        w = min(int(qty) * 3, max_w_ask)
        pygame.draw.rect(screen, col, (550, y - 10, w, 18), border_radius=3)
        qty_text = font.render(str(int(qty)), True, (255, 255, 255))
        text_x = 550 + 4
        screen.blit(qty_text, (text_x, y - 9))

    if order_book['bids']:
        y = px2y(order_book['bids'][0][0])
        pygame.draw.rect(screen, (0, 100, 170), (370, y - 13, 22, 24), 2)
    if order_book['asks']:
        y = px2y(order_book['asks'][0][0])
        pygame.draw.rect(screen, (180, 40, 80), (797, y - 13, 22, 24), 2)

    y = px2y(LTP)
    pygame.draw.line(screen, (44, 44, 200), (320, y), (760, y), 2)
    screen.blit(font.render(f"LTP {LTP}", 1, (44, 44, 200)), (785, y - 9))

    title_text = 'Simulating a Stock Exchange Order-Matching Engine ( Order Book )'
    title_surf = BIGFONT.render(title_text, True, (33, 44, 99))
    title_x = (WIDTH - title_surf.get_width()) // 2
    screen.blit(title_surf, (title_x, 16))
    screen.blit(font.render('BID (Buy)', 1, (10, 140, 10)), (280, 48))
    screen.blit(font.render('ASK (Sell)', 1, (160, 10, 10)), (700, 48))


def main():
    global TAKER_ID_COUNTER
    global ORDER_ID_COUNTER
    global WIDTH, HEIGHT
    global LTP
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Order Book Matching Game")
    clock = pygame.time.Clock()
    background_surface = make_background_surface(WIDTH, HEIGHT)

    order_book = new_order_book()
    trade_log = []
    fifo_log = []  # tuples: (order_id, side, price, filled_qty, taker)
    events_log = []  # general event log for UI
    # --- CSV Logging ---
    trades_csv_path = os.path.join(os.path.dirname(__file__), 'executed_trades.csv')
    events_csv_path = os.path.join(os.path.dirname(__file__), 'events_log.csv')

    def now_ts():
        return datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()

    def append_trades_to_csv(trades):
        # trades: list of tuples (price, qty, taker_label, counterparty_label, resting_oid, taker_id)
        file_exists = os.path.exists(trades_csv_path)
        with open(trades_csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    'timestamp_iso', 'price', 'qty', 'taker_label', 'counterparty_label',
                    'resting_side', 'resting_order_id', 'taker_id'
                ])
            ts = now_ts()
            for tr in trades:
                price, qty, taker_label, counterparty_label = tr[0], tr[1], tr[2], tr[3]
                resting_oid = tr[4] if len(tr) > 4 else ''
                taker_id = tr[5] if len(tr) > 5 else ''
                resting_side = 'Ask' if ('Seller' in counterparty_label) else 'Bid'
                writer.writerow([ts, price, qty, taker_label, counterparty_label, resting_side, resting_oid, taker_id])

    def append_event_to_csv(ev):
        file_exists = os.path.exists(events_csv_path)
        with open(events_csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['timestamp_iso','event','actor','taker_id','order_id','side','order_type','price','qty','filled_qty','status','note'])
            writer.writerow([
                ev.get('ts'), ev.get('event'), ev.get('actor'), ev.get('taker_id'), ev.get('order_id'), ev.get('side'),
                ev.get('order_type'), ev.get('price'), ev.get('qty'), ev.get('filled_qty'), ev.get('status'), ev.get('note')
            ])

    def log_event(ev):
        events_log.append(ev)
        append_event_to_csv(ev)


    # --- Player stats & costs ---
    player_orders_submitted = 0
    player_orders_fully_filled = 0
    player_orders_partially_filled = 0
    player_orders_unfilled_on_submit = 0
    last_order_brokerage = 0
    total_brokerage_paid = 0

    # Aggregated display state (per-price qty) for animations
    display_bids = {}
    display_asks = {}
    flash_bids = {}
    flash_asks = {}

    def aggregate_per_price(book):
        bids = {}
        asks = {}
        for px, qty, _player, _oid in book["bids"]:
            bids[px] = bids.get(px, 0) + qty
        for px, qty, _player, _oid in book["asks"]:
            asks[px] = asks.get(px, 0) + qty
        return bids, asks

    # Initialize display state to current order book
    tb, ta = aggregate_per_price(order_book)
    display_bids = {p: float(q) for p, q in tb.items()}
    display_asks = {p: float(q) for p, q in ta.items()}

    entry_typ = "LIMIT"
    entry_side = "Buy"
    entry_price = 1000
    entry_qty = 10
    running = True
    view_mode = 'executed'
    view_scroll_offset = 0
    # Demo playback state (step-by-step with 1s pause)
    demo_running = False
    demo_steps_left = 0
    demo_next_ms = 0

    while running:
        screen.blit(background_surface, (0, 0))

        # Update animation targets
        target_bids, target_asks = aggregate_per_price(order_book)

        # Animate bids
        bid_prices = set(target_bids.keys()) | set(display_bids.keys())
        for px in list(bid_prices):
            tgt = float(target_bids.get(px, 0))
            cur = float(display_bids.get(px, 0.0))
            if abs(tgt - cur) <= ANIM_STEP_PER_FRAME:
                new_val = tgt
            else:
                step = ANIM_STEP_PER_FRAME if tgt > cur else -ANIM_STEP_PER_FRAME
                new_val = cur + step
            if new_val <= 0 and tgt <= 0:
                display_bids.pop(px, None)
            else:
                display_bids[px] = new_val

        # Animate asks
        ask_prices = set(target_asks.keys()) | set(display_asks.keys())
        for px in list(ask_prices):
            tgt = float(target_asks.get(px, 0))
            cur = float(display_asks.get(px, 0.0))
            if abs(tgt - cur) <= ANIM_STEP_PER_FRAME:
                new_val = tgt
            else:
                step = ANIM_STEP_PER_FRAME if tgt > cur else -ANIM_STEP_PER_FRAME
                new_val = cur + step
            if new_val <= 0 and tgt <= 0:
                display_asks.pop(px, None)
            else:
                display_asks[px] = new_val

        # Decay flash timers
        for d in (flash_bids, flash_asks):
            rm = []
            for px, t in d.items():
                nt = t - 1
                if nt <= 0:
                    rm.append(px)
                else:
                    d[px] = nt
            for px in rm:
                d.pop(px, None)

        # Draw with animated state
        draw_orderbook(screen, order_book, display_bids, display_asks, flash_bids, flash_asks)

        xbase = WIDTH - 300
        ycur = 70
        # Order Entry panel
        panel_w = 280
        panel_h = 272
        panel_rect = pygame.Rect(xbase - 10, 36, panel_w, panel_h)
        pygame.draw.rect(screen, (245, 247, 252), panel_rect, border_radius=12)
        pygame.draw.rect(screen, (210, 216, 230), panel_rect, width=2, border_radius=12)
        title_surf = BIGFONT.render('Order Entry', True, (80, 80, 120))
        title_rect = title_surf.get_rect(midtop=(panel_rect.centerx, panel_rect.y + 8))
        screen.blit(title_surf, title_rect)

        limit_rect = pygame.Rect(xbase + 10, ycur, 120, 36)
        market_rect = pygame.Rect(xbase + 140, ycur, 120, 36)
        pygame.draw.rect(screen, (60, 140, 200) if entry_typ == "LIMIT" else (200, 206, 216), limit_rect, border_radius=10)
        pygame.draw.rect(screen, (60, 140, 200) if entry_typ == "MARKET" else (200, 206, 216), market_rect, border_radius=10)
        t1 = font.render("LIMIT", True, (255, 255, 255))
        t1r = t1.get_rect(center=limit_rect.center)
        screen.blit(t1, t1r)
        t2 = font.render("MARKET", True, (255, 255, 255))
        t2r = t2.get_rect(center=market_rect.center)
        screen.blit(t2, t2r)
        ycur += 50

        buy_rect = pygame.Rect(xbase + 10, ycur, 120, 36)
        sell_rect = pygame.Rect(xbase + 140, ycur, 120, 36)
        pygame.draw.rect(screen, (40, 160, 60) if entry_side == "Buy" else (200, 206, 216), buy_rect, border_radius=10)
        pygame.draw.rect(screen, (180, 40, 40) if entry_side == "Sell" else (200, 206, 216), sell_rect, border_radius=10)
        tb = font.render("Buy", True, (255, 255, 255))
        tbr = tb.get_rect(center=buy_rect.center)
        screen.blit(tb, tbr)
        ts = font.render("Sell", True, (255, 255, 255))
        tsr = ts.get_rect(center=sell_rect.center)
        screen.blit(ts, tsr)
        ycur += 50

        # --- Price Row with + / - Buttons ---
        price_rect = pygame.Rect(xbase + 10, ycur, 190, 36)
        plus_price = pygame.Rect(xbase + 210, ycur, 24, 36)
        minus_price = pygame.Rect(xbase + 240, ycur, 24, 36)
        pygame.draw.rect(screen, (240, 244, 255), price_rect, border_radius=10)
        pygame.draw.rect(screen, (60, 180, 90), plus_price, border_radius=8)
        pygame.draw.rect(screen, (200, 80, 80), minus_price, border_radius=8)
        ptxt = font.render((f"Price: {entry_price}" if entry_typ == "LIMIT" else "Market"), True, (44, 44, 99))
        ptxt_r = ptxt.get_rect(midleft=(price_rect.x + 12, price_rect.centery))
        screen.blit(ptxt, ptxt_r)
        ppls = font.render("+", True, (255, 255, 255))
        ppls_r = ppls.get_rect(center=plus_price.center)
        screen.blit(ppls, ppls_r)
        pmin = font.render("-", True, (255, 255, 255))
        pmin_r = pmin.get_rect(center=minus_price.center)
        screen.blit(pmin, pmin_r)
        ycur += 45

        # --- Quantity Row with + / - Buttons ---
        qty_rect = pygame.Rect(xbase + 10, ycur, 190, 36)
        plus_qty = pygame.Rect(xbase + 210, ycur, 24, 36)
        minus_qty = pygame.Rect(xbase + 240, ycur, 24, 36)
        pygame.draw.rect(screen, (255, 255, 230), qty_rect, border_radius=10)
        pygame.draw.rect(screen, (60, 180, 90), plus_qty, border_radius=8)
        pygame.draw.rect(screen, (200, 80, 80), minus_qty, border_radius=8)
        qtxt = font.render(f"Qty: {entry_qty}", True, (44, 44, 99))
        qtxt_r = qtxt.get_rect(midleft=(qty_rect.x + 12, qty_rect.centery))
        screen.blit(qtxt, qtxt_r)
        qpls = font.render("+", True, (255, 255, 255))
        qpls_r = qpls.get_rect(center=plus_qty.center)
        screen.blit(qpls, qpls_r)
        qmin = font.render("-", True, (255, 255, 255))
        qmin_r = qmin.get_rect(center=minus_qty.center)
        screen.blit(qmin, qmin_r)
        ycur += 45

        btn_rect = pygame.Rect(xbase + 10, ycur, 254, 40)
        pygame.draw.rect(screen, (70, 180, 100), btn_rect, border_radius=12)
        btxt = font.render("Place Order", True, (255, 255, 255))
        btxt_r = btxt.get_rect(center=btn_rect.center)
        screen.blit(btxt, btxt_r)
        # Utility buttons: Reset and Sample Book
        ycur = btn_rect.bottom + 8
        reset_rect = pygame.Rect(xbase + 10, ycur, 120, 32)
        sample_rect = pygame.Rect(xbase + 144, ycur, 120, 32)
        pygame.draw.rect(screen, (200, 80, 80), reset_rect, border_radius=10)
        pygame.draw.rect(screen, (80, 120, 200), sample_rect, border_radius=10)
        rtxt = font.render("Reset", True, (255, 255, 255))
        stxt = font.render("Sample Book", True, (255, 255, 255))
        screen.blit(rtxt, rtxt.get_rect(center=reset_rect.center))
        screen.blit(stxt, stxt.get_rect(center=sample_rect.center))
        ycur = sample_rect.bottom + 8
        demo_rect = pygame.Rect(xbase + 10, ycur, 254, 32)
        pygame.draw.rect(screen, (100, 160, 90), demo_rect, border_radius=10)
        dtxt = font.render("Run Demo (15 steps)", True, (255, 255, 255))
        screen.blit(dtxt, dtxt.get_rect(center=demo_rect.center))
        # Show demo status
        if demo_running:
            status_txt = font.render(f"Demo running... steps left: {demo_steps_left}", True, (70, 90, 110))
            screen.blit(status_txt, (xbase, demo_rect.bottom + 6))
            ycur = demo_rect.bottom + 26
        else:
            ycur = demo_rect.bottom + 12

        # --- Stats & Brokerage ---
        # Brokerage per order is fixed at ₹10 for player's orders
        # Currently open player's orders (left to be filled): count and qty
        player_open_entries = [e for e in order_book['bids'] + order_book['asks'] if e[2]]
        orders_left_to_be_filled = len(player_open_entries)
        qty_left_to_be_filled = sum(e[1] for e in player_open_entries)

        # System utilization: occupied price levels / total price levels in range
        occupied_levels = set(p for p, _q, _pl, _oid in order_book['bids']) | set(p for p, _q, _pl, _oid in order_book['asks'])
        total_levels = PRICE_MAX - PRICE_MIN + 1
        utilization_pct = (len(occupied_levels) / total_levels * 100.0) if total_levels > 0 else 0.0

        # Best bid/ask and level difference (spread in levels)
        best_bid = max((p for p, _q, _pl, _oid in order_book['bids']), default=None)
        best_ask = min((p for p, _q, _pl, _oid in order_book['asks']), default=None)
        level_diff = (best_ask - best_bid) if (best_bid is not None and best_ask is not None) else None

        # Stats panel - clean single-column list
        stats = [
            ("Last Traded Price (LTP)", f"{LTP}"),
            ("Orders submitted", f"{player_orders_submitted}"),
            ("Orders fully filled", f"{player_orders_fully_filled}"),
            ("Orders left open", f"{orders_left_to_be_filled}"),
            ("Orders partially filled", f"{player_orders_partially_filled}"),
            ("Orders unfilled on submit", f"{player_orders_unfilled_on_submit}"),
            ("Open qty left", f"{qty_left_to_be_filled}"),
            ("Brokerage (last)", f"{last_order_brokerage}"),
            ("Brokerage (total)", f"{total_brokerage_paid}"),
            ("System utilization", f"{utilization_pct:.1f}%"),
            ("Occupied levels", f"{len(occupied_levels)}"),
            ("Total levels", f"{total_levels}"),
            ("Min level permitted", f"{PRICE_MIN}"),
            ("Max level permitted", f"{PRICE_MAX}"),
            ("Price step size", f"{PRICE_TICK}"),
            ("Best bid", f"{best_bid if best_bid is not None else '-'}"),
            ("Best ask", f"{best_ask if best_ask is not None else '-'}"),
            ("Level diff (ask - bid)", f"{level_diff if level_diff is not None else '-'}"),
        ]
        panel_x = xbase
        panel_y = ycur
        panel_w = 280
        header_h = 30
        row_h = 22
        panel_h = header_h + len(stats) * row_h + 14
        # Panel background and border
        pygame.draw.rect(screen, (245, 247, 252), (panel_x, panel_y, panel_w, panel_h), border_radius=10)
        pygame.draw.rect(screen, (210, 216, 230), (panel_x, panel_y, panel_w, panel_h), width=2, border_radius=10)
        # Header strip
        pygame.draw.rect(screen, (228, 235, 247), (panel_x, panel_y, panel_w, header_h), border_radius=10)
        screen.blit(BIGFONT.render('Stats', 1, (60, 70, 100)), (panel_x + 10, panel_y + 4))
        # Rows (single-line label: value)
        text_x = panel_x + 12
        value_x = panel_x + panel_w - 12
        for i, (label, value) in enumerate(stats):
            y = panel_y + header_h + 8 + i * row_h
            # label
            screen.blit(font.render(label + ':', 1, (44, 44, 99)), (text_x, y))
            # right-aligned value
            val_surf = font.render(value, True, (44, 44, 99))
            screen.blit(val_surf, (value_x - val_surf.get_width(), y))
        ycur = panel_y + panel_h + 10

        # --- View toggle and lists ---
        toggle_x = 60
        toggle_y = HEIGHT - 260
        btn_exec = pygame.Rect(toggle_x, toggle_y, 180, 30)
        btn_pending = pygame.Rect(toggle_x + 190, toggle_y, 200, 30)
        btn_punched = pygame.Rect(toggle_x + 400, toggle_y, 200, 30)
        btn_history = pygame.Rect(toggle_x + 610, toggle_y, 200, 30)
        pygame.draw.rect(screen, (60, 140, 200) if view_mode == 'executed' else (190, 190, 190), btn_exec, border_radius=8)
        pygame.draw.rect(screen, (60, 140, 200) if view_mode == 'pending' else (190, 190, 190), btn_pending, border_radius=8)
        pygame.draw.rect(screen, (60, 140, 200) if view_mode == 'orders_punched' else (190, 190, 190), btn_punched, border_radius=8)
        pygame.draw.rect(screen, (60, 140, 200) if view_mode == 'orders_history' else (190, 190, 190), btn_history, border_radius=8)
        screen.blit(font.render("Executed Orders", 1, (255, 255, 255)), (btn_exec.x + 24, btn_exec.y + 6))
        screen.blit(font.render("Pending Orders", 1, (255, 255, 255)), (btn_pending.x + 34, btn_pending.y + 6))
        screen.blit(font.render("All Orders Punched", 1, (255, 255, 255)), (btn_punched.x + 28, btn_punched.y + 6))
        screen.blit(font.render("Trade Logs", 1, (255, 255, 255)), (btn_history.x + 28, btn_history.y + 6))

        # Calculate how many rows can fit in the bottom panel dynamically
        rows_area_px = 220 - 60 - 8  # total bottom height - header offset - bottom padding
        rows_per_view = max(1, rows_area_px // 22)

        if view_mode == 'executed':
            # Executed table from trade events to capture partial fills and FIFO
            header_y = HEIGHT - 220
            screen.blit(BIGFONT.render('Executed Orders (FIFO filled)', 1, (90, 90, 110)), (60, header_y))
            cols = [60, 200, 270, 330, 410, 620, 760, 840]
            col_titles = ['Time', 'Taker', 'Qty', 'Price', 'Counterparty', 'RestingSide', 'OID', 'TID']
            pygame.draw.rect(screen, (235, 240, 250), (cols[0]-4, header_y+30, 820, 24), border_radius=4)
            for c, title in zip(cols, col_titles):
                screen.blit(font.render(title, 1, (60, 60, 90)), (c, header_y + 32))
            trade_events = [ev for ev in events_log if ev.get('event') == 'trade']
            visible_count = rows_per_view
            n = len(trade_events)
            start = min(view_scroll_offset, max(0, n - visible_count))
            for i in range(0, min(visible_count, n - start)):
                ev = trade_events[-1 - (start + i)]
                ts = ev.get('ts', '')
                taker = ev.get('actor', '')
                qty = ev.get('qty', '')
                price = ev.get('price', '')
                counterparty = ev.get('note', '')
                resting_side = 'Ask' if ('Seller' in counterparty) else 'Bid'
                oid = ev.get('order_id', '')
                tid = ev.get('taker_id', '')
                y = header_y + 60 + i * 22
                if i % 2 == 0:
                    pygame.draw.rect(screen, (248, 248, 248), (cols[0]-4, y-2, 820, 22))
                text_col = (40, 140, 80) if taker == 'You' else (70, 70, 70)
                screen.blit(font.render(str(ts.split('T')[-1].split('.')[0].split('+')[0][:8]), 1, (70, 70, 70)), (cols[0], y))
                screen.blit(font.render(str(taker), 1, text_col), (cols[1], y))
                screen.blit(font.render(str(qty), 1, (70, 70, 70)), (cols[2], y))
                screen.blit(font.render(str(price), 1, (70, 70, 70)), (cols[3], y))
                screen.blit(font.render(str(counterparty), 1, (70, 70, 70)), (cols[4], y))
                screen.blit(font.render(str(resting_side), 1, (70, 70, 70)), (cols[5], y))
                screen.blit(font.render(str(oid), 1, (70, 70, 70)), (cols[6], y))
                screen.blit(font.render(str(tid), 1, (70, 70, 70)), (cols[7], y))
        elif view_mode == 'orders_punched':
            # All Orders Punched (submissions only)
            header_y = HEIGHT - 220
            screen.blit(BIGFONT.render('All Orders Punched', 1, (90, 90, 110)), (60, header_y))
            cols = [60, 180, 260, 340, 420, 510, 600, 690]
            col_titles = ['Time', 'Actor', 'Side', 'Type', 'Qty', 'Price', 'OID', 'TID']
            pygame.draw.rect(screen, (235, 240, 250), (cols[0]-4, header_y+30, 780, 24), border_radius=4)
            for c, title in zip(cols, col_titles):
                screen.blit(font.render(title, 1, (60, 60, 90)), (c, header_y + 32))
            submit_events = [ev for ev in events_log if ev.get('event') == 'submit']
            visible_count = rows_per_view
            n = len(submit_events)
            start = min(view_scroll_offset, max(0, n - visible_count))
            for i in range(0, min(visible_count, n - start)):
                ev = submit_events[-1 - (start + i)]
                y = header_y + 60 + i * 22
                if i % 2 == 0:
                    pygame.draw.rect(screen, (248, 248, 248), (cols[0]-4, y-2, 780, 22))
                screen.blit(font.render(str(ev.get('ts','')).split('T')[-1].split('.')[0].split('+')[0][:8], 1, (70, 70, 70)), (cols[0], y))
                screen.blit(font.render(str(ev.get('actor', '')), 1, (70, 70, 70)), (cols[1], y))
                screen.blit(font.render(str(ev.get('side', '')), 1, (70, 70, 70)), (cols[2], y))
                screen.blit(font.render(str(ev.get('order_type', '')), 1, (70, 70, 70)), (cols[3], y))
                screen.blit(font.render(str(ev.get('qty', '')), 1, (70, 70, 70)), (cols[4], y))
                screen.blit(font.render(str(ev.get('price', '')), 1, (70, 70, 70)), (cols[5], y))
                screen.blit(font.render(str(ev.get('order_id', '')), 1, (70, 70, 70)), (cols[6], y))
                screen.blit(font.render(str(ev.get('taker_id', '')), 1, (70, 70, 70)), (cols[7], y))
        elif view_mode == 'orders_history':
            # Trade Logs (all events)
            header_y = HEIGHT - 220
            screen.blit(BIGFONT.render('Trade Logs', 1, (90, 90, 110)), (60, header_y))
            cols = [60, 140, 220, 300, 360, 430, 500, 580, 660, 730, 800, 860]
            col_titles = ['Time', 'Event', 'Actor', 'Side', 'Type', 'Price', 'Qty', 'Filled', 'Status', 'OID', 'TID', 'Note']
            pygame.draw.rect(screen, (235, 240, 250), (cols[0]-4, header_y+30, 820, 24), border_radius=4)
            for c, title in zip(cols, col_titles):
                screen.blit(font.render(title, 1, (60, 60, 90)), (c, header_y + 32))
            all_rows = events_log
            visible_count = rows_per_view
            n = len(all_rows)
            start = min(view_scroll_offset, max(0, n - visible_count))
            for i in range(0, min(visible_count, n - start)):
                ev = all_rows[-1 - (start + i)]
                y = header_y + 60 + i * 22
                if i % 2 == 0:
                    pygame.draw.rect(screen, (248, 248, 248), (cols[0]-4, y-2, 820, 22))
                screen.blit(font.render(str(ev.get('ts','')).split('T')[-1].split('.')[0].split('+')[0][:8], 1, (70, 70, 70)), (cols[0], y))
                screen.blit(font.render(str(ev.get('event', '')), 1, (70, 70, 70)), (cols[1], y))
                screen.blit(font.render(str(ev.get('actor', '')), 1, (70, 70, 70)), (cols[2], y))
                screen.blit(font.render(str(ev.get('side', '')), 1, (70, 70, 70)), (cols[3], y))
                screen.blit(font.render(str(ev.get('order_type', '')), 1, (70, 70, 70)), (cols[4], y))
                screen.blit(font.render(str(ev.get('price', '')), 1, (70, 70, 70)), (cols[5], y))
                screen.blit(font.render(str(ev.get('qty', '')), 1, (70, 70, 70)), (cols[6], y))
                screen.blit(font.render(str(ev.get('filled_qty', '')), 1, (70, 70, 70)), (cols[7], y))
                screen.blit(font.render(str(ev.get('status', '')), 1, (70, 70, 70)), (cols[8], y))
                screen.blit(font.render(str(ev.get('order_id', '')), 1, (70, 70, 70)), (cols[9], y))
                screen.blit(font.render(str(ev.get('taker_id', '')), 1, (70, 70, 70)), (cols[10], y))
                screen.blit(font.render(str(ev.get('note', '')), 1, (70, 70, 70)), (cols[11], y))
        else:
            # Pending Orders view only
            header_y = HEIGHT - 220
            screen.blit(BIGFONT.render('Pending Orders (live)', 1, (90, 90, 110)), (60, header_y))
            cols = [60, 160, 260, 340, 420]
            col_titles = ['OID', 'Owner', 'Side', 'Qty', 'Price']
            pygame.draw.rect(screen, (235, 240, 250), (cols[0]-4, header_y+30, 500, 24), border_radius=4)
            for c, title in zip(cols, col_titles):
                screen.blit(font.render(title, 1, (60, 60, 90)), (c, header_y + 32))
            # Build and sort pending by price-time priority: bids (price desc, OID asc), asks (price asc, OID asc)
            bid_rows = []
            ask_rows = []
            for p, q, is_pl, oid in order_book['bids']:
                bid_rows.append((oid, 'You' if is_pl else 'Bot', 'Bid', q, p))
            for p, q, is_pl, oid in order_book['asks']:
                ask_rows.append((oid, 'You' if is_pl else 'Bot', 'Ask', q, p))
            bid_rows.sort(key=lambda r: (-r[4], r[0]))  # price desc, OID asc
            ask_rows.sort(key=lambda r: (r[4], r[0]))   # price asc, OID asc
            all_pending = bid_rows + ask_rows
            visible_count = rows_per_view
            n = len(all_pending)
            start = min(view_scroll_offset, max(0, n - visible_count))
            for i in range(0, min(visible_count, n - start)):
                row = all_pending[start + i]
                y = header_y + 60 + i * 22
                if i % 2 == 0:
                    pygame.draw.rect(screen, (248, 248, 248), (cols[0]-4, y-2, 500, 22))
                screen.blit(font.render(str(row[0]), 1, (70, 70, 70)), (cols[0], y))
                screen.blit(font.render(str(row[1]), 1, (70, 70, 70)), (cols[1], y))
                screen.blit(font.render(str(row[2]), 1, (70, 70, 70)), (cols[2], y))
                screen.blit(font.render(str(row[3]), 1, (70, 70, 70)), (cols[3], y))
                screen.blit(font.render(str(row[4]), 1, (70, 70, 70)), (cols[4], y))

        # --- Event Handling ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                # Toggle buttons
                toggle_x = 60
                toggle_y = HEIGHT - 260
                btn_exec = pygame.Rect(toggle_x, toggle_y, 180, 30)
                btn_pending = pygame.Rect(toggle_x + 190, toggle_y, 200, 30)
                btn_punched = pygame.Rect(toggle_x + 400, toggle_y, 200, 30)
                btn_history = pygame.Rect(toggle_x + 610, toggle_y, 200, 30)
                if btn_exec.collidepoint(mx, my):
                    view_mode = 'executed'
                    view_scroll_offset = 0
                    continue
                if btn_pending.collidepoint(mx, my):
                    view_mode = 'pending'
                    view_scroll_offset = 0
                    continue
                if btn_punched.collidepoint(mx, my):
                    view_mode = 'orders_punched'
                    view_scroll_offset = 0
                    continue
                if btn_history.collidepoint(mx, my):
                    view_mode = 'orders_history'
                    view_scroll_offset = 0
                    continue
                if limit_rect.collidepoint(mx, my):
                    entry_typ = "LIMIT"
                elif market_rect.collidepoint(mx, my):
                    entry_typ = "MARKET"
                elif buy_rect.collidepoint(mx, my):
                    entry_side = "Buy"
                elif sell_rect.collidepoint(mx, my):
                    entry_side = "Sell"
                elif plus_price.collidepoint(mx, my) and entry_typ == "LIMIT":
                    entry_price = min(PRICE_MAX, entry_price + 1)
                elif minus_price.collidepoint(mx, my) and entry_typ == "LIMIT":
                    entry_price = max(PRICE_MIN, entry_price - 1)
                elif plus_qty.collidepoint(mx, my):
                    entry_qty = min(100, entry_qty + 1)
                elif minus_qty.collidepoint(mx, my):
                    entry_qty = max(1, entry_qty - 1)
                elif btn_rect.collidepoint(mx, my):
                    # Player submits an order; brokerage applies per submission
                    player_orders_submitted += 1
                    # Brokerage applies only if any part gets filled
                    last_order_brokerage = 0
                    # Assign a taker ID to this submission
                    taker_id = TAKER_ID_COUNTER
                    TAKER_ID_COUNTER += 1
                    # Log submission
                    log_event({'ts': now_ts(), 'event': 'submit', 'actor': 'You', 'taker_id': taker_id,
                               'order_id': '', 'side': entry_side, 'order_type': entry_typ, 'price': entry_price, 'qty': entry_qty,
                               'filled_qty': 0, 'status': 'submitted', 'note': ''})
                    if entry_typ == "LIMIT":
                        tr, fifo = place_limit_order(order_book, entry_side.lower(), entry_price, entry_qty, True, taker_id)
                    else:
                        tr, fifo = place_market_order(order_book, entry_side.lower(), entry_qty, True, taker_id)
                    if tr:
                        trade_log.extend(tr)
                        fifo_log.extend(fifo)
                        append_trades_to_csv(tr)
                        # Update LTP to last executed trade price
                        try:
                            LTP = tr[-1][0]
                        except Exception:
                            pass
                        # Flash the consumed side levels
                        for price, _qty, _who, _cp, _roid, _tid in tr:
                            if entry_side == "Buy":
                                flash_asks[price] = FLASH_FRAMES
                            else:
                                flash_bids[price] = FLASH_FRAMES
                        # Determine if the submitted order was fully filled
                        filled_qty = sum(q for _p, q, _w, _c, _roid, _tid in tr)
                        if filled_qty >= entry_qty:
                            player_orders_fully_filled += 1
                            status = 'filled'
                        elif filled_qty > 0:
                            player_orders_partially_filled += 1
                            status = 'partial'
                        else:
                            player_orders_unfilled_on_submit += 1
                            status = 'open'
                        # Apply brokerage only when some quantity filled
                        if filled_qty > 0:
                            last_order_brokerage = 10
                            total_brokerage_paid += 10
                        # Log result event
                        log_event({'ts': now_ts(), 'event': 'result', 'actor': 'You', 'taker_id': taker_id,
                                   'order_id': '', 'side': entry_side, 'order_type': entry_typ, 'price': entry_price, 'qty': entry_qty,
                                   'filled_qty': filled_qty, 'status': status, 'note': ''})
                        # Log each trade as event
                        for (p, q, taker_label, cp_label, roid, tid) in tr:
                            log_event({'ts': now_ts(), 'event': 'trade', 'actor': taker_label, 'taker_id': tid,
                                       'order_id': roid, 'side': entry_side, 'order_type': entry_typ, 'price': p, 'qty': q,
                                       'filled_qty': q, 'status': 'executed', 'note': cp_label})
                    else:
                        player_orders_unfilled_on_submit += 1
                        log_event({'ts': now_ts(), 'event': 'result', 'actor': 'You', 'taker_id': taker_id,
                                   'order_id': '', 'side': entry_side, 'order_type': entry_typ, 'price': entry_price, 'qty': entry_qty,
                                   'filled_qty': 0, 'status': 'open', 'note': ''})
                # Utility buttons behavior
                elif 'reset_rect' in locals() and reset_rect.collidepoint(mx, my):
                    # Reset entire simulation state
                    ORDER_ID_COUNTER = 1
                    TAKER_ID_COUNTER = 1
                    order_book = new_order_book()
                    trade_log = []
                    fifo_log = []
                    events_log = []
                    player_orders_submitted = 0
                    player_orders_fully_filled = 0
                    player_orders_partially_filled = 0
                    player_orders_unfilled_on_submit = 0
                    last_order_brokerage = 0
                    total_brokerage_paid = 0
                    LTP = 1000
                    entry_typ = "LIMIT"; entry_side = "Buy"; entry_price = 1000; entry_qty = 10
                    # Reset display/animations
                    display_bids = {}
                    display_asks = {}
                    flash_bids = {}
                    flash_asks = {}
                    view_mode = 'executed'
                    view_scroll_offset = 0
                    continue
                elif 'sample_rect' in locals() and sample_rect.collidepoint(mx, my):
                    # Generate a sample order book snapshot
                    ORDER_ID_COUNTER = 1
                    order_book = new_order_book()
                    # helper to append resting
                    def add_resting(side, price, qty, is_player=False):
                        global ORDER_ID_COUNTER
                        if side == 'bid':
                            order_book['bids'].append((price, qty, is_player, ORDER_ID_COUNTER))
                        else:
                            order_book['asks'].append((price, qty, is_player, ORDER_ID_COUNTER))
                        # log a submit for visibility
                        tid = TAKER_ID_COUNTER
                        log_event({'ts': now_ts(), 'event': 'submit', 'actor': ('You' if is_player else 'Bot'), 'taker_id': tid,
                                   'order_id': ORDER_ID_COUNTER, 'side': ('Buy' if side=='bid' else 'Sell'), 'order_type': 'LIMIT',
                                   'price': price, 'qty': qty, 'filled_qty': 0, 'status': 'submitted', 'note': ''})
                        ORDER_ID_COUNTER += 1
                    # Populate richer sample: multiple levels, mix of Bot and You (more depth)
                    # Bids (Buy side)
                    add_resting('bid', 1000, 8, True)    # You at best bid
                    add_resting('bid', 1000, 4, False)
                    add_resting('bid', 999,  6, False)
                    add_resting('bid', 999,  5, True)
                    add_resting('bid', 998, 10, False)
                    add_resting('bid', 998,  7, False)
                    add_resting('bid', 997, 12, False)
                    add_resting('bid', 996, 14, False)
                    add_resting('bid', 995, 11, False)
                    # Asks (Sell side)
                    add_resting('ask', 1001, 7, False)   # Best ask
                    add_resting('ask', 1001, 3, True)
                    add_resting('ask', 1002, 5, False)
                    add_resting('ask', 1002, 9, False)
                    add_resting('ask', 1003, 9, False)
                    add_resting('ask', 1003, 5, False)
                    add_resting('ask', 1004, 10, False)
                    add_resting('ask', 1005, 12, False)
                    add_resting('ask', 1006, 10, False)
                    sort_book(order_book)
                    # Sync display instantly
                    tb, ta = aggregate_per_price(order_book)
                    display_bids = {p: float(q) for p, q in tb.items()}
                    display_asks = {p: float(q) for p, q in ta.items()}
                    flash_bids = {}
                    flash_asks = {}
                    # Set LTP at mid reference
                    LTP = 1000
                    view_mode = 'executed'
                    view_scroll_offset = 0
                    # Auto-run two demo trades (buy then sell) to showcase LTP and flashes
                    # Increment TAKER_ID_COUNTER and run demo BUY
                    demo_tid_buy = TAKER_ID_COUNTER; TAKER_ID_COUNTER += 1
                    log_event({'ts': now_ts(), 'event': 'submit', 'actor': 'Bot', 'taker_id': demo_tid_buy,
                               'order_id': '', 'side': 'Buy', 'order_type': 'MARKET', 'price': '', 'qty': 5,
                               'filled_qty': 0, 'status': 'submitted', 'note': 'demo trade'})
                    tr_demo_b, _ = place_market_order(order_book, 'buy', 5, False, demo_tid_buy)
                    if tr_demo_b:
                        trade_log.extend(tr_demo_b)
                        append_trades_to_csv(tr_demo_b)
                        try:
                            LTP = tr_demo_b[-1][0]
                        except Exception:
                            pass
                        filled_b = sum(q for _p, q, _tl, _cp, _oid, _tid in tr_demo_b)
                        log_event({'ts': now_ts(), 'event': 'result', 'actor': 'Bot', 'taker_id': demo_tid_buy,
                                   'order_id': '', 'side': 'Buy', 'order_type': 'MARKET', 'price': '', 'qty': 5,
                                   'filled_qty': filled_b, 'status': ('filled' if filled_b>=5 else ('partial' if filled_b>0 else 'open')), 'note': 'demo trade'})
                        for price, _qty, _who, _cp, _roid, _tid in tr_demo_b:
                            flash_asks[price] = FLASH_FRAMES
                            log_event({'ts': now_ts(), 'event': 'trade', 'actor': _who, 'taker_id': _tid,
                                       'order_id': _roid, 'side': 'Buy', 'order_type': 'MARKET', 'price': price, 'qty': _qty,
                                       'filled_qty': _qty, 'status': 'executed', 'note': _cp})
                    # Increment TAKER_ID_COUNTER and run demo SELL
                    demo_tid_sell = TAKER_ID_COUNTER; TAKER_ID_COUNTER += 1
                    log_event({'ts': now_ts(), 'event': 'submit', 'actor': 'Bot', 'taker_id': demo_tid_sell,
                               'order_id': '', 'side': 'Sell', 'order_type': 'MARKET', 'price': '', 'qty': 6,
                               'filled_qty': 0, 'status': 'submitted', 'note': 'demo trade'})
                    tr_demo_s, _ = place_market_order(order_book, 'sell', 6, False, demo_tid_sell)
                    if tr_demo_s:
                        trade_log.extend(tr_demo_s)
                        append_trades_to_csv(tr_demo_s)
                        try:
                            LTP = tr_demo_s[-1][0]
                        except Exception:
                            pass
                        filled_s = sum(q for _p, q, _tl, _cp, _oid, _tid in tr_demo_s)
                        log_event({'ts': now_ts(), 'event': 'result', 'actor': 'Bot', 'taker_id': demo_tid_sell,
                                   'order_id': '', 'side': 'Sell', 'order_type': 'MARKET', 'price': '', 'qty': 6,
                                   'filled_qty': filled_s, 'status': ('filled' if filled_s>=6 else ('partial' if filled_s>0 else 'open')), 'note': 'demo trade'})
                        for price, _qty, _who, _cp, _roid, _tid in tr_demo_s:
                            flash_bids[price] = FLASH_FRAMES
                            log_event({'ts': now_ts(), 'event': 'trade', 'actor': _who, 'taker_id': _tid,
                                       'order_id': _roid, 'side': 'Sell', 'order_type': 'MARKET', 'price': price, 'qty': _qty,
                                       'filled_qty': _qty, 'status': 'executed', 'note': _cp})
                    # Refresh display targets after trades
                    tb, ta = aggregate_per_price(order_book)
                    display_bids = {p: float(q) for p, q in tb.items()}
                    display_asks = {p: float(q) for p, q in ta.items()}
                    continue
                elif 'demo_rect' in locals() and demo_rect.collidepoint(mx, my):
                    # Start step-by-step demo (10 steps, 1 second apart)
                    demo_running = True
                    demo_steps_left = 15
                    demo_next_ms = pygame.time.get_ticks() + 1000
                    view_mode = 'executed'
                    view_scroll_offset = 0
                    continue
            elif event.type == pygame.MOUSEWHEEL:
                # positive y => scroll up (older); negative y => scroll down (newer)
                # Normalize: we want up to increase offset, down to decrease
                delta = -event.y
                # Recompute dynamic visible rows to match draw area
                rows_area_px = 220 - 60 - 8
                visible = max(1, rows_area_px // 22)
                if view_mode == 'executed':
                    total_items = sum(1 for ev in events_log if ev.get('event') == 'trade')
                elif view_mode == 'orders_punched':
                    total_items = sum(1 for ev in events_log if ev.get('event') == 'submit')
                elif view_mode == 'orders_history':
                    total_items = len(events_log)
                else:
                    total_items = len(order_book['bids']) + len(order_book['asks'])
                max_start = max(0, total_items - visible)
                view_scroll_offset = max(0, min(max_start, view_scroll_offset + (3 * delta)))

        # --- Bot Orders ---
        if pygame.key.get_pressed()[pygame.K_SPACE]:
            for _ in range(3):
                bp = random.randint(PRICE_MIN, PRICE_MAX)
                sp = random.randint(PRICE_MIN, PRICE_MAX)
                bq = random.randint(3, 12)
                sq = random.randint(3, 12)
                tid_b = TAKER_ID_COUNTER; TAKER_ID_COUNTER += 1
                tid_s = TAKER_ID_COUNTER; TAKER_ID_COUNTER += 1
                # Log bot submissions
                log_event({'ts': now_ts(), 'event': 'submit', 'actor': 'Bot', 'taker_id': tid_b,
                           'order_id': '', 'side': 'Buy', 'order_type': 'LIMIT', 'price': bp, 'qty': bq,
                           'filled_qty': 0, 'status': 'submitted', 'note': ''})
                log_event({'ts': now_ts(), 'event': 'submit', 'actor': 'Bot', 'taker_id': tid_s,
                           'order_id': '', 'side': 'Sell', 'order_type': 'LIMIT', 'price': sp, 'qty': sq,
                           'filled_qty': 0, 'status': 'submitted', 'note': ''})
                trb, fib = place_limit_order(order_book, 'buy', bp, bq, False, tid_b)
                trs, fia = place_limit_order(order_book, 'sell', sp, sq, False, tid_s)
                if trb:
                    trade_log.extend(trb)
                    fifo_log.extend(fib)
                    append_trades_to_csv(trb)
                    # Update LTP to last executed trade price
                    try:
                        LTP = trb[-1][0]
                    except Exception:
                        pass
                    filled_qty_b = sum(q for _p, q, _tl, _cp, _oid, _tid in trb)
                    log_event({'ts': now_ts(), 'event': 'result', 'actor': 'Bot', 'taker_id': tid_b,
                               'order_id': '', 'side': 'Buy', 'order_type': 'LIMIT', 'price': bp, 'qty': bq,
                               'filled_qty': filled_qty_b, 'status': ('filled' if filled_qty_b>=bq else ('partial' if filled_qty_b>0 else 'open')), 'note': ''})
                    for price, _qty, _who, _cp, _roid, _tid in trb:
                        # buy consumes asks
                        flash_asks[price] = FLASH_FRAMES
                        log_event({'ts': now_ts(), 'event': 'trade', 'actor': _who, 'taker_id': _tid,
                                   'order_id': _roid, 'side': 'Buy', 'order_type': 'LIMIT', 'price': price, 'qty': _qty,
                                   'filled_qty': _qty, 'status': 'executed', 'note': _cp})
                if trs:
                    trade_log.extend(trs)
                    fifo_log.extend(fia)
                    append_trades_to_csv(trs)
                    # Update LTP to last executed trade price
                    try:
                        LTP = trs[-1][0]
                    except Exception:
                        pass
                    filled_qty_s = sum(q for _p, q, _tl, _cp, _oid, _tid in trs)
                    log_event({'ts': now_ts(), 'event': 'result', 'actor': 'Bot', 'taker_id': tid_s,
                               'order_id': '', 'side': 'Sell', 'order_type': 'LIMIT', 'price': sp, 'qty': sq,
                               'filled_qty': filled_qty_s, 'status': ('filled' if filled_qty_s>=sq else ('partial' if filled_qty_s>0 else 'open')), 'note': ''})
                    for price, _qty, _who, _cp, _roid, _tid in trs:
                        # sell consumes bids
                        flash_bids[price] = FLASH_FRAMES
                        log_event({'ts': now_ts(), 'event': 'trade', 'actor': _who, 'taker_id': _tid,
                                   'order_id': _roid, 'side': 'Sell', 'order_type': 'LIMIT', 'price': price, 'qty': _qty,
                                   'filled_qty': _qty, 'status': 'executed', 'note': _cp})

        pygame.display.flip()
        clock.tick(FPS)

        # --- Demo step runner (after frame flip to maintain cadence) ---
        if demo_running and pygame.time.get_ticks() >= demo_next_ms:
            # Execute one random action
            act_is_limit = (random.random() < 0.6)
            side = 'buy' if (random.random() < 0.5) else 'sell'
            qty = random.randint(3, 10)
            tid = TAKER_ID_COUNTER; TAKER_ID_COUNTER += 1
            if act_is_limit:
                px = max(PRICE_MIN, min(PRICE_MAX, LTP + random.randint(-2, 2)))
                log_event({'ts': now_ts(), 'event': 'submit', 'actor': 'Bot', 'taker_id': tid,
                           'order_id': '', 'side': ('Buy' if side=='buy' else 'Sell'), 'order_type': 'LIMIT',
                           'price': px, 'qty': qty, 'filled_qty': 0, 'status': 'submitted', 'note': 'demo'})
                tr_d, _ = place_limit_order(order_book, side, px, qty, False, tid)
            else:
                log_event({'ts': now_ts(), 'event': 'submit', 'actor': 'Bot', 'taker_id': tid,
                           'order_id': '', 'side': ('Buy' if side=='buy' else 'Sell'), 'order_type': 'MARKET',
                           'price': '', 'qty': qty, 'filled_qty': 0, 'status': 'submitted', 'note': 'demo'})
                tr_d, _ = place_market_order(order_book, side, qty, False, tid)

            if tr_d:
                trade_log.extend(tr_d)
                append_trades_to_csv(tr_d)
                try:
                    LTP = tr_d[-1][0]
                except Exception:
                    pass
                filled = sum(q for _p, q, _tl, _cp, _oid, _tid in tr_d)
                log_event({'ts': now_ts(), 'event': 'result', 'actor': 'Bot', 'taker_id': tid,
                           'order_id': '', 'side': ('Buy' if side=='buy' else 'Sell'), 'order_type': ('LIMIT' if act_is_limit else 'MARKET'),
                           'price': (px if act_is_limit else ''), 'qty': qty, 'filled_qty': filled,
                           'status': ('filled' if filled>=qty else ('partial' if filled>0 else 'open')), 'note': 'demo'})
                for price, _qty, _who, _cp, _roid, _tid in tr_d:
                    if side == 'buy':
                        flash_asks[price] = FLASH_FRAMES
                    else:
                        flash_bids[price] = FLASH_FRAMES
                    log_event({'ts': now_ts(), 'event': 'trade', 'actor': _who, 'taker_id': _tid,
                               'order_id': _roid, 'side': ('Buy' if side=='buy' else 'Sell'), 'order_type': ('LIMIT' if act_is_limit else 'MARKET'),
                               'price': price, 'qty': _qty, 'filled_qty': _qty, 'status': 'executed', 'note': _cp})
            else:
                log_event({'ts': now_ts(), 'event': 'result', 'actor': 'Bot', 'taker_id': tid,
                           'order_id': '', 'side': ('Buy' if side=='buy' else 'Sell'), 'order_type': ('LIMIT' if act_is_limit else 'MARKET'),
                           'price': (px if act_is_limit else ''), 'qty': qty, 'filled_qty': 0, 'status': 'open', 'note': 'demo'})

            # Sync displays
            tb, ta = aggregate_per_price(order_book)
            display_bids = {p: float(q) for p, q in tb.items()}
            display_asks = {p: float(q) for p, q in ta.items()}

            demo_steps_left -= 1
            if demo_steps_left <= 0:
                demo_running = False
            else:
                demo_next_ms = pygame.time.get_ticks() + 1000


if __name__ == "__main__":
    main()
