import tkinter as tk
from tkinter import ttk
import serial
import threading
import csv
import time
from collections import deque
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# --- CONFIGURATION ---
SERIAL_PORT = '/dev/ttyUSB0'
BAUD_RATE = 115200
MAX_HISTORY = 60 # Shows the last 60 data points on the graph

# --- SHARED DATA STORAGE ---
times = deque([0]*MAX_HISTORY, maxlen=MAX_HISTORY)

# Store historical data for all 7 variables constantly
history = {
    "V_IN": deque([0]*MAX_HISTORY, maxlen=MAX_HISTORY),
    "I_IN": deque([0]*MAX_HISTORY, maxlen=MAX_HISTORY),
    "V_OUT": deque([0]*MAX_HISTORY, maxlen=MAX_HISTORY),
    "I_OUT": deque([0]*MAX_HISTORY, maxlen=MAX_HISTORY),
    "TEMP_C": deque([0]*MAX_HISTORY, maxlen=MAX_HISTORY),
    "P_OUT": deque([0]*MAX_HISTORY, maxlen=MAX_HISTORY),
    "BATT_CURR": deque([0]*MAX_HISTORY, maxlen=MAX_HISTORY)
}

latest_data = {
    "V_IN": 0.0, "I_IN": 0.0, 
    "V_OUT": 0.0, "I_OUT": 0.0, 
    "TEMP_C": 0.0, "P_OUT": 0.0,
    "BATT_CURR": 0.0
}

is_logging = False
csv_file = None
csv_writer = None
start_time = time.time()

# --- CHECKSUM VERIFICATION ---
def verify_checksum(payload, checksum_hex):
    calc = 0
    for char in payload:
        calc ^= ord(char)
    try:
        return calc == int(checksum_hex, 16)
    except ValueError:
        return False

# --- BACKGROUND SERIAL THREAD ---
def read_serial_data():
    global latest_data, is_logging, csv_writer
    
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    except Exception as e:
        print(f"Could not open serial port: {e}")
        return

    while True:
        try:
            line = ser.readline().decode('ascii', errors='ignore').strip()
            
            if line.startswith('$') and '*' in line:
                payload, cs_str = line[1:].split('*')
                
                if verify_checksum(payload, cs_str):
                    vals = payload.split(',')
                    # Checked for exactly 7 values now
                    if len(vals) == 7:
                        # Parse the data
                        latest_data["V_IN"] = float(vals[0])
                        latest_data["I_IN"] = float(vals[1])
                        latest_data["V_OUT"] = float(vals[2])
                        latest_data["I_OUT"] = float(vals[3])
                        latest_data["TEMP_C"] = float(vals[4])
                        latest_data["P_OUT"] = float(vals[5])
                        latest_data["BATT_CURR"] = float(vals[6])
                        
                        current_t = time.time() - start_time
                        
                        # Update graph arrays
                        times.append(current_t)
                        history["V_IN"].append(latest_data["V_IN"])
                        history["I_IN"].append(latest_data["I_IN"])
                        history["V_OUT"].append(latest_data["V_OUT"])
                        history["I_OUT"].append(latest_data["I_OUT"])
                        history["TEMP_C"].append(latest_data["TEMP_C"])
                        history["P_OUT"].append(latest_data["P_OUT"])
                        history["BATT_CURR"].append(latest_data["BATT_CURR"])
                        
                        # Write to CSV if logging is active
                        if is_logging and csv_writer:
                            csv_writer.writerow([
                                f"{current_t:.2f}", 
                                latest_data["V_IN"], latest_data["I_IN"],
                                latest_data["V_OUT"], latest_data["I_OUT"],
                                latest_data["TEMP_C"], latest_data["P_OUT"],
                                latest_data["BATT_CURR"]
                            ])
                            csv_file.flush()
                            
        except Exception as e:
            print(f"Serial read error: {e}")
            time.sleep(1)

# --- GUI CLASS ---
class TelemetryDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("BCM4414 Telemetry Dashboard")
        self.root.geometry("850x500")

        # Top Frame for Buttons and Text
        control_frame = tk.Frame(root)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        # Labels for Live Data
        self.lbl_v = tk.Label(control_frame, text="V_OUT: 0.00", font=("Arial", 12, "bold"), fg="blue")
        self.lbl_v.pack(side=tk.LEFT, padx=10)
        
        self.lbl_i = tk.Label(control_frame, text="I_OUT: 0.00", font=("Arial", 12, "bold"), fg="red")
        self.lbl_i.pack(side=tk.LEFT, padx=10)
        
        self.lbl_batt = tk.Label(control_frame, text="BATT_CURR: 0.00", font=("Arial", 12, "bold"), fg="purple")
        self.lbl_batt.pack(side=tk.LEFT, padx=10)
        
        self.lbl_t = tk.Label(control_frame, text="TEMP: 0.0", font=("Arial", 12, "bold"))
        self.lbl_t.pack(side=tk.LEFT, padx=10)

        # CSV Logging Button
        self.btn_csv = tk.Button(control_frame, text="Start CSV Log", command=self.toggle_csv, bg="green", fg="white", font=("Arial", 10, "bold"))
        self.btn_csv.pack(side=tk.RIGHT, padx=5)

        # Graph Selection Frame
        select_frame = tk.Frame(root)
        select_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=0)
        
        # Variable options mapping (including BATT_CURR)
        self.options = ["V_IN", "I_IN", "V_OUT", "I_OUT", "TEMP_C", "P_OUT", "BATT_CURR"]
        
        tk.Label(select_frame, text="Top Chart:").pack(side=tk.LEFT, padx=5)
        self.top_var = tk.StringVar(value="V_OUT")
        self.top_menu = ttk.Combobox(select_frame, textvariable=self.top_var, values=self.options, state="readonly", width=12)
        self.top_menu.pack(side=tk.LEFT, padx=5)

        tk.Label(select_frame, text="Bottom Chart:").pack(side=tk.LEFT, padx=15)
        self.bot_var = tk.StringVar(value="BATT_CURR")
        self.bot_menu = ttk.Combobox(select_frame, textvariable=self.bot_var, values=self.options, state="readonly", width=12)
        self.bot_menu.pack(side=tk.LEFT, padx=5)

        # Matplotlib Figure
        self.fig = Figure(figsize=(8, 4), dpi=100)
        self.ax1 = self.fig.add_subplot(211) 
        self.ax2 = self.fig.add_subplot(212) 
        
        self.fig.tight_layout(pad=2.0)

        # Initialize blank lines
        self.line_top, = self.ax1.plot(times, history[self.top_var.get()], 'b-')
        self.ax1.grid(True)

        self.line_bot, = self.ax2.plot(times, history[self.bot_var.get()], 'r-')
        self.ax2.set_xlabel("Time (s)")
        self.ax2.grid(True)

        # Embed plot in Tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        # Start the GUI update loop
        self.update_gui()

    def toggle_csv(self):
        global is_logging, csv_file, csv_writer
        
        if not is_logging:
            filename = f"bcm_log_{int(time.time())}.csv"
            csv_file = open(filename, 'w', newline='')
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(["Time(s)", "V_IN", "I_IN", "V_OUT", "I_OUT", "TEMP_C", "P_OUT", "BATT_CURR"])
            is_logging = True
            self.btn_csv.config(text="Stop CSV Log", bg="red")
            print(f"Started logging to {filename}")
        else:
            is_logging = False
            if csv_file:
                csv_file.close()
            self.btn_csv.config(text="Start CSV Log", bg="green")
            print("Stopped logging.")

    def update_gui(self):
        # Update text labels
        self.lbl_v.config(text=f"V_OUT: {latest_data['V_OUT']:.2f} V")
        self.lbl_i.config(text=f"I_OUT: {latest_data['I_OUT']:.2f} A")
        self.lbl_batt.config(text=f"BATT_CURR: {latest_data['BATT_CURR']:.2f}")
        self.lbl_t.config(text=f"TEMP: {latest_data['TEMP_C']:.1f} C")

        # Get current dropdown selections
        top_sel = self.top_var.get()
        bot_sel = self.bot_var.get()

        # Update Top Chart
        self.line_top.set_xdata(times)
        self.line_top.set_ydata(history[top_sel])
        self.ax1.set_ylabel(top_sel)
        self.ax1.relim()
        self.ax1.autoscale_view()

        # Update Bottom Chart
        self.line_bot.set_xdata(times)
        self.line_bot.set_ydata(history[bot_sel])
        self.ax2.set_ylabel(bot_sel)
        self.ax2.relim()
        self.ax2.autoscale_view()

        self.canvas.draw()

        # Reschedule this function
        self.root.after(500, self.update_gui)

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    serial_thread = threading.Thread(target=read_serial_data, daemon=True)
    serial_thread.start()

    root = tk.Tk()
    app = TelemetryDashboard(root)
    
    def on_closing():
        global is_logging, csv_file
        is_logging = False
        if csv_file:
            csv_file.close()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
