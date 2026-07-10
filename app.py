# ==========================================
# 𓋹 PHARAOH GOLD BOT - تطبيق الويب الفرعوني 𓋹
# تحليل الذهب باستخدام SMC + ICT + نماذج فنية
# ==========================================

import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import matplotlib.pyplot as plt
import io
from datetime import datetime, timedelta
import requests
import json
import os
import warnings
import numpy as np
warnings.filterwarnings('ignore')

# ==========================================
# 1. جلب سعر الذهب الفوري (من GoldAPI أو yfinance)
# ==========================================

def get_spot_price():
    """جلب سعر الذهب الفوري من GoldAPI، وفي حال الفشل يستخدم yfinance"""
    try:
        # محاولة استخدام GoldAPI
        api_key = st.secrets.get("GOLD_API_KEY", "goldapi-2e91d85dc02f06984d99b2cb3dd9066c-io")
        url = "https://www.goldapi.io/api/XAU/USD"
        headers = {"x-access-token": api_key, "Content-Type": "application/json"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                'price': float(data.get('price', 0)),
                'timestamp': data.get('timestamp'),
                'currency': data.get('currency', 'USD'),
                'high': float(data.get('high', 0)),
                'low': float(data.get('low', 0)),
                'change': float(data.get('change', 0))
            }
    except Exception as e:
        print(f"⚠️ GoldAPI فشل: {e}")

    # البديل: استخدام yfinance
    try:
        ticker = yf.Ticker("GC=F")
        data = ticker.history(period="1d", interval="1m")
        if not data.empty:
            last = data.iloc[-1]
            return {
                'price': float(last['Close']),
                'timestamp': datetime.now().isoformat(),
                'currency': 'USD',
                'high': float(data['High'].max()),
                'low': float(data['Low'].min()),
                'change': float((last['Close'] - data['Close'].iloc[0]) / data['Close'].iloc[0] * 100)
            }
    except:
        pass
    return None

# ==========================================
# 2. تحليل SMC و ICT (Smart Money Concepts)
# ==========================================

def analyze_smc_ict(df):
    """إضافة مؤشرات SMC و ICT إلى DataFrame"""
    df = df.copy()
    # تهيئة الأعمدة
    df['order_block_bullish'] = False
    df['order_block_bearish'] = False
    df['fvg_bullish'] = False
    df['fvg_bearish'] = False
    df['liquidity_sweep_bullish'] = False
    df['liquidity_sweep_bearish'] = False
    df['bos_bullish'] = False
    df['bos_bearish'] = False
    df['in_discount'] = False
    df['in_premium'] = False
    df['mss_bullish'] = False
    df['mss_bearish'] = False

    # Order Blocks
    for i in range(3, len(df)):
        # Bullish Order Block
        if df['close'].iloc[i] > df['open'].iloc[i]:
            body = df['close'].iloc[i] - df['open'].iloc[i]
            avg_range = (df['high'].iloc[i-3:i].max() - df['low'].iloc[i-3:i].min()) / 3
            if body > avg_range and df['close'].iloc[i-1] < df['open'].iloc[i-1]:
                df.loc[df.index[i-1], 'order_block_bullish'] = True
        # Bearish Order Block
        if df['close'].iloc[i] < df['open'].iloc[i]:
            body = df['open'].iloc[i] - df['close'].iloc[i]
            avg_range = (df['high'].iloc[i-3:i].max() - df['low'].iloc[i-3:i].min()) / 3
            if body > avg_range and df['close'].iloc[i-1] > df['open'].iloc[i-1]:
                df.loc[df.index[i-1], 'order_block_bearish'] = True

    # Fair Value Gaps (FVG)
    for i in range(2, len(df)):
        if df['low'].iloc[i] > df['high'].iloc[i-2]:
            df.loc[df.index[i], 'fvg_bullish'] = True
        if df['high'].iloc[i] < df['low'].iloc[i-2]:
            df.loc[df.index[i], 'fvg_bearish'] = True

    # Liquidity Sweeps
    for i in range(10, len(df)):
        recent_lows = df['low'].iloc[i-10:i].tolist()
        if df['low'].iloc[i] < min(recent_lows[:-1]):
            df.loc[df.index[i], 'liquidity_sweep_bullish'] = True
        recent_highs = df['high'].iloc[i-10:i].tolist()
        if df['high'].iloc[i] > max(recent_highs[:-1]):
            df.loc[df.index[i], 'liquidity_sweep_bearish'] = True

    # Break of Structure (BOS)
    for i in range(5, len(df)):
        if df['close'].iloc[i] > df['high'].iloc[i-5:i].max():
            df.loc[df.index[i], 'bos_bullish'] = True
        if df['close'].iloc[i] < df['low'].iloc[i-5:i].min():
            df.loc[df.index[i], 'bos_bearish'] = True

    # Discount / Premium zones
    for i in range(50, len(df)):
        range_high = df['high'].iloc[i-50:i].max()
        range_low = df['low'].iloc[i-50:i].min()
        if range_high != range_low:
            discount = range_low + (range_high - range_low) * 0.382
            premium = range_high - (range_high - range_low) * 0.382
            if df['close'].iloc[i] <= discount:
                df.loc[df.index[i], 'in_discount'] = True
            if df['close'].iloc[i] >= premium:
                df.loc[df.index[i], 'in_premium'] = True

    # Market Structure Shift (MSS)
    for i in range(3, len(df)):
        if df['bos_bearish'].iloc[i-1] and df['close'].iloc[i] > df['high'].iloc[i-2:i].max():
            df.loc[df.index[i], 'mss_bullish'] = True
        if df['bos_bullish'].iloc[i-1] and df['close'].iloc[i] < df['low'].iloc[i-2:i].min():
            df.loc[df.index[i], 'mss_bearish'] = True

    return df

# ==========================================
# 3. كشف النماذج الفنية (Chart Patterns)
# ==========================================

def find_peaks_troughs(series, order=5):
    """إيجاد القمم والقيعان المحلية"""
    peaks = []
    troughs = []
    for i in range(order, len(series) - order):
        if all(series[i] > series[i-j] for j in range(1, order+1)) and all(series[i] > series[i+j] for j in range(1, order+1)):
            peaks.append((i, series[i]))
        if all(series[i] < series[i-j] for j in range(1, order+1)) and all(series[i] < series[i+j] for j in range(1, order+1)):
            troughs.append((i, series[i]))
    return peaks, troughs

def detect_head_shoulders(df, lookback=50):
    """كشف نموذج الرأس والكتفين"""
    if len(df) < lookback:
        return None, 0
    recent_highs = df['high'].iloc[-lookback:].values
    peaks, _ = find_peaks_troughs(recent_highs, order=3)
    if len(peaks) >= 3:
        head_idx = np.argmax([p[1] for p in peaks])
        if head_idx > 0 and head_idx < len(peaks) - 1:
            left_shoulder = peaks[head_idx - 1][1]
            head = peaks[head_idx][1]
            right_shoulder = peaks[head_idx + 1][1]
            if head > left_shoulder and head > right_shoulder:
                if abs(left_shoulder - right_shoulder) / left_shoulder < 0.05:
                    return "HEAD_AND_SHOULDERS", 5
    return None, 0

def detect_double_top_bottom(df, lookback=50):
    """كشف نموذج القمة المزدوجة أو القاع المزدوج"""
    if len(df) < lookback:
        return None, 0
    recent_highs = df['high'].iloc[-lookback:].values
    recent_lows = df['low'].iloc[-lookback:].values
    peaks, _ = find_peaks_troughs(recent_highs, order=3)
    _, troughs = find_peaks_troughs(recent_lows, order=3)
    
    if len(peaks) >= 2:
        last_two_peaks = sorted(peaks[-2:], key=lambda x: x[0])
        if abs(last_two_peaks[-1][1] - last_two_peaks[-2][1]) / last_two_peaks[-2][1] < 0.03:
            return "DOUBLE_TOP", 4
    if len(troughs) >= 2:
        last_two_troughs = sorted(troughs[-2:], key=lambda x: x[0])
        if abs(last_two_troughs[-1][1] - last_two_troughs[-2][1]) / last_two_troughs[-2][1] < 0.03:
            return "DOUBLE_BOTTOM", 4
    return None, 0

def detect_triangle_pattern(df, lookback=40):
    """كشف نموذج المثلث"""
    if len(df) < lookback:
        return None, 0
    recent_data = df.iloc[-lookback:]
    highs = recent_data['high'].values
    lows = recent_data['low'].values
    x = np.arange(len(highs))
    slope_highs = np.polyfit(x, highs, 1)[0]
    slope_lows = np.polyfit(x, lows, 1)[0]
    if slope_lows > 0.01 and abs(slope_highs) < 0.005:
        return "ASCENDING_TRIANGLE", 3
    if slope_highs < -0.01 and abs(slope_lows) < 0.005:
        return "DESCENDING_TRIANGLE", 3
    return None, 0

def analyze_chart_patterns(df):
    """تحليل جميع النماذج الفنية وإرجاع القائمة"""
    patterns = []
    total_score = 0
    
    pattern, score = detect_head_shoulders(df)
    if pattern:
        patterns.append({"pattern": pattern, "score": score, "direction": "BEARISH"})
        total_score += score
    
    pattern, score = detect_double_top_bottom(df)
    if pattern:
        direction = "BEARISH" if "DOUBLE_TOP" in pattern else "BULLISH"
        patterns.append({"pattern": pattern, "score": score, "direction": direction})
        total_score += score
    
    pattern, score = detect_triangle_pattern(df)
    if pattern:
        direction = "BULLISH" if "ASCENDING" in pattern else "BEARISH"
        patterns.append({"pattern": pattern, "score": score, "direction": direction})
        total_score += score
    
    return patterns, total_score

# ==========================================
# 4. إدارة المخاطر والمستويات
# ==========================================

def get_confirmed_levels(df, current_price, lookback=30):
    """استخراج مستويات الدعم والمقاومة المؤكدة"""
    peaks = []
    for i in range(lookback, len(df)):
        if i+1 < len(df):
            if df['high'].iloc[i] > df['high'].iloc[i-1] and df['high'].iloc[i] > df['high'].iloc[i+1]:
                peaks.append(df['high'].iloc[i])
        else:
            if df['high'].iloc[i] > df['high'].iloc[i-1]:
                peaks.append(df['high'].iloc[i])
    
    troughs = []
    for i in range(lookback, len(df)):
        if i+1 < len(df):
            if df['low'].iloc[i] < df['low'].iloc[i-1] and df['low'].iloc[i] < df['low'].iloc[i+1]:
                troughs.append(df['low'].iloc[i])
        else:
            if df['low'].iloc[i] < df['low'].iloc[i-1]:
                troughs.append(df['low'].iloc[i])
    
    confirmed_resistance = min([p for p in peaks if p > current_price]) if peaks else current_price + 30
    confirmed_support = max([t for t in troughs if t < current_price]) if troughs else current_price - 30
    
    higher_resistance = sorted([p for p in peaks if p > confirmed_resistance])[:2] if peaks else [confirmed_resistance + 25, confirmed_resistance + 50]
    lower_support = sorted([t for t in troughs if t < confirmed_support], reverse=True)[:2] if troughs else [confirmed_support - 25, confirmed_support - 50]
    
    return {
        'confirmed_resistance': confirmed_resistance,
        'confirmed_support': confirmed_support,
        'higher_resistance': higher_resistance,
        'lower_support': lower_support
    }

def get_smart_targets_confirmed(df, current_price, signal_action="BUY"):
    """تحديد الأهداف الذكية بناءً على المستويات"""
    levels = get_confirmed_levels(df, current_price)
    targets = []
    
    if signal_action == "BUY":
        if levels['confirmed_resistance'] > current_price:
            targets.append(levels['confirmed_resistance'])
        if levels['higher_resistance'] and levels['higher_resistance'][0] > current_price:
            targets.append(levels['higher_resistance'][0])
        if len(levels['higher_resistance']) > 1 and levels['higher_resistance'][1] > current_price:
            targets.append(levels['higher_resistance'][1])
        else:
            targets.append(levels['confirmed_resistance'] + (levels['confirmed_resistance'] - current_price) * 2)
        targets = [t for t in targets if t > current_price]
        targets = sorted(set(targets))[:3]
    else:
        if levels['confirmed_support'] < current_price:
            targets.append(levels['confirmed_support'])
        if levels['lower_support'] and levels['lower_support'][0] < current_price:
            targets.append(levels['lower_support'][0])
        if len(levels['lower_support']) > 1 and levels['lower_support'][1] < current_price:
            targets.append(levels['lower_support'][1])
        else:
            targets.append(levels['confirmed_support'] - (current_price - levels['confirmed_support']) * 2)
        targets = [t for t in targets if t < current_price]
        targets = sorted(set(targets), reverse=True)[:3]
    
    if not targets:
        if signal_action == "BUY":
            targets = [current_price + 20, current_price + 40, current_price + 60]
        else:
            targets = [current_price - 20, current_price - 40, current_price - 60]
    
    return targets

def get_initial_stop_confirmed(df, current_price, signal_action="BUY"):
    """تحديد وقف الخسارة الابتدائي"""
    levels = get_confirmed_levels(df, current_price)
    if signal_action == "BUY":
        stop_loss = levels['confirmed_support']
        stop_loss = stop_loss - (current_price - stop_loss) * 0.1
    else:
        stop_loss = levels['confirmed_resistance']
        stop_loss = stop_loss + (stop_loss - current_price) * 0.1
    return stop_loss

# ==========================================
# 5. تحليل الصفقة الجارية
# ==========================================

def analyze_active_trade_smart(trade, current_price, df=None):
    """تحليل الصفقة الجارية وإعطاء اقتراحات ذكية"""
    direction = trade['direction']
    entry = trade['entry_price']
    highest = trade.get('highest_price', entry)
    lowest = trade.get('lowest_price', entry)
    
    if direction == "BUY" and current_price > highest:
        highest = current_price
    elif direction == "SELL" and current_price < lowest:
        lowest = current_price
    
    if direction == "BUY":
        profit = current_price - entry
        profit_pct = (profit / entry) * 100
    else:
        profit = entry - current_price
        profit_pct = (profit / entry) * 100
    
    if profit_pct >= 1.5:
        profit_level = "VERY_HIGH"
        level_text = "ربح كبير جداً"
    elif profit_pct >= 0.8:
        profit_level = "HIGH"
        level_text = "ربح جيد"
    elif profit_pct >= 0.3:
        profit_level = "MEDIUM"
        level_text = "ربح متوسط"
    elif profit_pct > 0:
        profit_level = "LOW"
        level_text = "ربح بسيط"
    else:
        profit_level = "LOSS"
        level_text = "خسارة"
    
    # كشف الانعكاس
    reversal_detected = False
    reversal_text = ""
    if df is not None and len(df) > 5 and 'atr' in df.columns and not df['atr'].isna().all():
        atr = df['atr'].iloc[-1] if not pd.isna(df['atr'].iloc[-1]) else 10
        last_candles = df['close'].iloc[-5:].values
        if len(last_candles) >= 2:
            if direction == "BUY":
                if last_candles[-1] < last_candles[-2] and (last_candles[-2] - last_candles[-1]) > atr * 0.5:
                    reversal_detected = True
                    reversal_text = "⚠️ شمعة انعكاس هابط - احتمال انعكاس"
            else:
                if last_candles[-1] > last_candles[-2] and (last_candles[-1] - last_candles[-2]) > atr * 0.5:
                    reversal_detected = True
                    reversal_text = "⚠️ شمعة انعكاس صاعد - احتمال ارتداد"
    
    # الوقف المتحرك
    trailing_stop = None
    if direction == "BUY":
        if highest > entry:
            trailing_stop = highest - (highest * 0.005)
            trailing_stop = max(trailing_stop, entry)
    else:
        if lowest < entry:
            trailing_stop = lowest + (lowest * 0.005)
            trailing_stop = min(trailing_stop, entry)
    
    # الاقتراحات
    suggestions = []
    if profit_level == "LOSS":
        suggestions.append("🔴 خروج من الصفقة (حماية رأس المال)")
    elif profit_level == "VERY_HIGH":
        suggestions.append("🛡️ نقل الوقف إلى نقطة الدخول (تأمين الأرباح)")
        if trailing_stop:
            suggestions.append(f"📈 تفعيل الوقف المتحرك عند ${trailing_stop:.2f}")
        suggestions.append("💰 إغلاق 50% من الصفقة وجري الباقي")
    elif profit_level == "HIGH":
        suggestions.append("🛡️ نقل الوقف إلى نقطة الدخول")
        if trailing_stop:
            suggestions.append(f"📈 تفعيل الوقف المتحرك عند ${trailing_stop:.2f}")
    elif profit_level == "MEDIUM":
        if trailing_stop:
            suggestions.append(f"📈 تفعيل الوقف المتحرك عند ${trailing_stop:.2f}")
        suggestions.append("🔍 مراقبة السوق عن كثب")
    else:
        suggestions.append("🔍 انتظار مزيد من التأكيدات")
    
    if reversal_detected:
        suggestions.append(reversal_text)
        suggestions.append("⚡ فكر في الخروج الجزئي لحماية الأرباح")
    
    return {
        'profit': profit,
        'profit_pct': profit_pct,
        'profit_level': profit_level,
        'level_text': level_text,
        'highest': highest,
        'lowest': lowest,
        'reversal_detected': reversal_detected,
        'reversal_text': reversal_text,
        'trailing_stop': trailing_stop,
        'suggestions': suggestions
    }

# ==========================================
# 6. تطبيق Streamlit (الواجهة الرئيسية)
# ==========================================

st.set_page_config(
    page_title="بوت الذهب الفرعوني",
    page_icon="🪙",
    layout="wide"
)

# CSS مخصص للهواتف
st.markdown("""
    <style>
    .main {
        padding: 0rem 1rem;
    }
    .stButton button {
        width: 100%;
        border-radius: 8px;
        background-color: #d4af37;
        color: black;
        font-weight: bold;
    }
    .stSelectbox, .stTextInput, .stNumberInput {
        direction: rtl;
    }
    </style>
""", unsafe_allow_html=True)

# العنوان الرئيسي
st.markdown("""
    <h1 style='text-align: center; color: #d4af37; font-size: 2.5rem;'>
        𓋹 بوت الذهب الفرعوني 𓋹
    </h1>
    <p style='text-align: center; font-size: 1.1rem;'>
        تحليل ذكي باستخدام SMC + ICT + نماذج فنية
    </p>
    <hr style='border-color: #d4af37;'>
""", unsafe_allow_html=True)

# ==========================================
# تهيئة حالة الجلسة
# ==========================================

if "df" not in st.session_state:
    st.session_state.df = None
if "current_trade" not in st.session_state:
    st.session_state.current_trade = None
if "trades" not in st.session_state:
    st.session_state.trades = []
if "price_data" not in st.session_state:
    st.session_state.price_data = None
if "show_form" not in st.session_state:
    st.session_state.show_form = False

# ==========================================
# الشريط الجانبي (الإعدادات)
# ==========================================

with st.sidebar:
    st.header("⚙️ الإعدادات")
    symbol = st.text_input("الرمز", value="GC=F")
    interval = st.selectbox("الفاصل الزمني", ["1m", "5m", "15m", "1h", "1d"], index=2)
    period = st.selectbox("الفترة", ["1d", "5d", "1mo", "3mo"], index=1)
    
    if st.button("🔄 تحديث البيانات", use_container_width=True):
        with st.spinner("جاري تحميل البيانات..."):
            try:
                df = yf.download(symbol, period=period, interval=interval)
                if len(df) > 0:
                    st.session_state.df = df
                    st.success("✅ تم التحديث!")
                else:
                    st.error("❌ لم يتم جلب بيانات")
            except Exception as e:
                st.error(f"خطأ: {e}")
    
    st.markdown("---")
    st.subheader("📋 إدارة الصفقات")
    if st.button("➕ صفقة جديدة", use_container_width=True):
        st.session_state.show_form = not st.session_state.show_form

# ==========================================
# الأعمدة الرئيسية
# ==========================================

col1, col2 = st.columns([2, 1])

# ==========================================
# العمود الأيسر: السعر والتحليل
# ==========================================

with col1:
    # --- السعر الفوري ---
    st.subheader("💰 السعر الفوري")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("جلب السعر", use_container_width=True):
            spot = get_spot_price()
            if spot:
                st.session_state.price_data = spot
            else:
                st.warning("⚠️ تعذر جلب السعر")
    
    if st.session_state.price_data:
        spot = st.session_state.price_data
        with col_a:
            st.metric("السعر", f"${spot['price']:.2f}", f"{spot['change']:+.2f}%")
        with col_b:
            st.metric("أعلى", f"${spot['high']:.2f}")
        with col_c:
            st.metric("أدنى", f"${spot['low']:.2f}")
    else:
        st.info("اضغط 'جلب السعر' لعرض آخر سعر")

    # --- الرسم البياني ---
    st.subheader("📈 تحليل فني")
    if st.session_state.df is not None and not st.session_state.df.empty:
        df = st.session_state.df.copy()
        df = analyze_smc_ict(df)
        
        # رسم الشارت
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(df.index, df['close'], label='السعر', color='gold', linewidth=1.5)
        ax.set_title(f'تحليل الذهب - {symbol}', fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)
        st.pyplot(fig)
        
        # عرض النماذج المكتشفة
        patterns, score = analyze_chart_patterns(df)
        if patterns:
            st.write("**📐 النماذج المكتشفة:**")
            for p in patterns:
                st.write(f"- {p['pattern']} ({p['direction']}) - قوة: {p['score']}/5")
        else:
            st.write("لا توجد نماذج حالياً")
    else:
        st.info("حدّث البيانات من الشريط الجانبي")

# ==========================================
# العمود الأيمن: الإشارات والصفقات
# ==========================================

with col2:
    # --- حالة السوق ---
    st.subheader("📊 حالة السوق")
    # حالة السوق مبسطة (يمكن تطويرها)
    st.info("🟢 السوق مفتوح (افتراضي)")

    # --- إشارة تداول ---
    st.subheader("🎯 إشارة تداول")
    if st.button("توليد إشارة", use_container_width=True):
        if st.session_state.df is not None and not st.session_state.df.empty:
            df = st.session_state.df
            last = df.iloc[-1]
            current_price = last['close']
            
            # منطق بسيط للإشارة (يمكن تحسينه)
            if last['close'] > last['open']:
                action = "BUY"
            elif last['close'] < last['open']:
                action = "SELL"
            else:
                action = "NEUTRAL"
            
            if action != "NEUTRAL":
                targets = get_smart_targets_confirmed(df, current_price, action)
                stop = get_initial_stop_confirmed(df, current_price, action)
                st.success(f"📌 الاتجاه: {action}")
                st.write(f"💰 الدخول: ${current_price:.2f}")
                st.write(f"🛑 وقف الخسارة: ${stop:.2f}")
                st.write("🎯 الأهداف: " + ", ".join([f"${t:.2f}" for t in targets[:3]]))
            else:
                st.warning("⚠️ لا توجد إشارة واضحة")
        else:
            st.warning("⚠️ حدّث البيانات أولاً")

    # --- الصفقة الجارية ---
    st.subheader("📌 الصفقة الجارية")
    if st.session_state.current_trade:
        trade = st.session_state.current_trade
        spot = get_spot_price()
        if spot:
            current = spot['price']
            analysis = analyze_active_trade_smart(trade, current, st.session_state.df)
            
            st.write(f"**الاتجاه:** {trade['direction']}")
            st.write(f"**الدخول:** ${trade['entry_price']:.2f}")
            st.write(f"**الحالي:** ${current:.2f}")
            st.write(f"**الربح:** {analysis['profit']:+.2f} ({analysis['profit_pct']:+.2f}%)")
            st.write(f"**المستوى:** {analysis['level_text']}")
            
            st.write("**💡 الاقتراحات:**")
            for sugg in analysis['suggestions']:
                st.write(f"- {sugg}")
            
            if st.button("❌ إغلاق الصفقة", use_container_width=True):
                st.session_state.current_trade = None
                st.success("✅ تم إغلاق الصفقة")
                st.experimental_rerun()
        else:
            st.warning("⚠️ تعذر جلب السعر")
    else:
        st.write("لا توجد صفقة جارية")

    # --- نموذج إضافة صفقة ---
    if st.session_state.show_form:
        with st.form("new_trade_form"):
            st.subheader("➕ تفاصيل الصفقة")
            direction = st.selectbox("الاتجاه", ["BUY", "SELL"])
            entry = st.number_input("سعر الدخول", value=0.0, format="%.2f")
            stop = st.number_input("وقف الخسارة", value=0.0, format="%.2f")
            targets_input = st.text_input("الأهداف (مفصولة بفاصلة)", placeholder="مثال: 1950, 1960, 1970")
            submitted = st.form_submit_button("إضافة الصفقة")
            
            if submitted:
                if entry > 0 and stop > 0:
                    targets_list = [float(x.strip()) for x in targets_input.split(",") if x.strip()]
                    trade = {
                        "entry_price": entry,
                        "direction": direction,
                        "stop_loss": stop,
                        "targets": targets_list,
                        "highest_price": entry,
                        "lowest_price": entry
                    }
                    st.session_state.current_trade = trade
                    st.success("✅ تم إضافة الصفقة!")
                    st.session_state.show_form = False
                    st.experimental_rerun()
                else:
                    st.error("⚠️ يرجى إدخال سعر الدخول ووقف الخسارة")

# ==========================================
# تذييل الصفحة
# ==========================================

st.markdown("""
    <hr style='border-color: #d4af37;'>
    <p style='text-align: center; color: #888; font-size: 0.9rem;'>
        𓋹 بوت الذهب الفرعوني - الإصدار النهائي 𓋹<br>
        البيانات مقدمة من Yahoo Finance & GoldAPI
    </p>
""", unsafe_allow_html=True)

# نهاية الملف
