import os
import json
import threading
import subprocess
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# Percorsi file di configurazione e log
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "stm8_config.json")
LOG_FILE    = os.path.join(os.path.dirname(__file__), "stm8_programmer.log")

# Lista dei modelli STM8 per STVP_CmdLine.exe
STM8_MODELS = [
    "STM8S003K3", "STM8S105", "STM8S207",
    "STM8L151",  "STM8L152", "STM8AF52A",
    "STM8AF6220"
]

class Stm8ProgrammerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("STM8 Programmer (SWIM)")
        self.geometry("900x820")
        self._log_queue = queue.Queue()

        # configurazione di default
        self.config = {
            "cli_path": os.path.join("C:\\", "tools", "stvp", "STVP_CmdLine.exe"),
            "model":    STM8_MODELS[0],
            "files":    {"prog": "", "data": "", "opt": ""},
            "logo_path": os.path.join(os.path.dirname(__file__), "logo.png")
        }
        self._load_config()

        # registra avvio sessione su file di log
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n--- Avvio Sessione STM8 ---\n")

        self._build_ui()
        self.after(100, self._process_log_queue)
        self.after(500, self._update_preview)

    def _load_config(self):
        if os.path.isfile(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self.config.update(saved)
            except Exception:
                pass

    def _save_config(self):
        try:
            to_save = {
                "cli_path": self.cli_var.get(),
                "model":    self.model_var.get(),
                "files":    {k: v.get() for k, v in self.file_vars.items()},
                "logo_path": self.config.get("logo_path", "")
            }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(to_save, f, indent=2)
        except Exception:
            pass

    def _build_ui(self):
        # Logo in alto, se esiste
        logo_path = self.config.get("logo_path", "")
        if os.path.isfile(logo_path):
            try:
                self.logo_img = tk.PhotoImage(file=logo_path)
                ttk.Label(self, image=self.logo_img).pack(side=tk.TOP, pady=10)
            except Exception:
                pass

        # Notebook principale
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Tab Programmazione
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Programmazione")

        row = 0
        # Path STVP_CmdLine.exe
        ttk.Label(frame, text="STVP_CmdLine.exe:").grid(row=row, column=0, sticky=tk.W)
        self.cli_var = tk.StringVar(value=self.config["cli_path"])
        ttk.Entry(frame, textvariable=self.cli_var, width=70).grid(row=row, column=1, padx=5)
        ttk.Button(frame, text="Sfoglia", command=self._browse_cli).grid(row=row, column=2)
        row += 1

        # Modello STM8
        ttk.Label(frame, text="Modello STM8:").grid(row=row, column=0, sticky=tk.W, pady=(8,0))
        self.model_var = tk.StringVar(value=self.config["model"])
        ttk.Combobox(
            frame, textvariable=self.model_var, values=STM8_MODELS,
            state="readonly", width=30
        ).grid(row=row, column=1, padx=5, sticky=tk.W)
        row += 1

        # FileProgramma, FileDati, FileOpzioni
        self.file_vars = {
            "prog": tk.StringVar(value=self.config["files"]["prog"]),
            "data": tk.StringVar(value=self.config["files"]["data"]),
            "opt":  tk.StringVar(value=self.config["files"]["opt"])
        }
        labels = {
            "prog": "FileProgramma (.s19/.hex):",
            "data": "FileDati      (.hex):",
            "opt":  "FileOpzioni   (.hex):"
        }
        for key in ("prog", "data", "opt"):
            ttk.Label(frame, text=labels[key]).grid(row=row, column=0, sticky=tk.W, pady=4)
            ttk.Entry(frame, textvariable=self.file_vars[key], width=70).grid(row=row, column=1, padx=5)
            ttk.Button(frame, text="Sfoglia", command=lambda k=key: self._browse_file(k))\
               .grid(row=row, column=2)
            row += 1

        # Avvia Programmazione, Progressbar e Stato
        self.btn_start = ttk.Button(frame, text="Avvia Programmazione", command=self._start_thread)
        self.btn_start.grid(row=row, column=0, columnspan=2, pady=12, sticky=tk.W)

        self.prog_bar = ttk.Progressbar(frame, mode="indeterminate")
        self.prog_bar.grid(row=row, column=2, sticky=tk.EW, padx=5)

        ttk.Label(frame, text="Stato:").grid(row=row, column=3, sticky=tk.E, padx=(20,2))
        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(frame, textvariable=self.status_var, foreground="blue")\
           .grid(row=row, column=4, sticky=tk.W)

        frame.grid_columnconfigure(1, weight=1)
        row += 1

        # Anteprima comando
        ttk.Label(frame, text="Comando da eseguire:").grid(
            row=row, column=0, sticky=tk.NW, pady=(10,0)
        )
        self.preview_txt = scrolledtext.ScrolledText(
            frame, height=3, wrap=tk.WORD, state=tk.DISABLED
        )
        self.preview_txt.grid(
            row=row, column=1, columnspan=4, sticky=tk.EW, padx=5, pady=(10,0)
        )
        row += 1

        # Verbose Output
        ttk.Label(frame, text="Verbose Output:").grid(
            row=row, column=0, sticky=tk.NW, pady=(10,0)
        )
        self.verbose_txt = scrolledtext.ScrolledText(
            frame, height=15, wrap=tk.NONE, state=tk.DISABLED
        )
        self.verbose_txt.grid(
            row=row, column=1, columnspan=4, sticky=tk.EW, padx=5, pady=(10,0)
        )
        row += 1

        # Tab Log (su file)
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="Log")
        self.log_txt = scrolledtext.ScrolledText(log_frame, state=tk.DISABLED)
        self.log_txt.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _browse_cli(self):
        path = filedialog.askopenfilename(
            title="Seleziona STVP_CmdLine.exe",
            filetypes=[("Eseguibile", "*.exe"), ("Tutti i file", "*.*")]
        )
        if path:
            self.cli_var.set(path)

    def _browse_file(self, key):
        ftypes = [("S19/HEX", "*.s19 *.hex")] if key == "prog" else [("HEX", "*.hex")]
        path = filedialog.askopenfilename(title=f"Scegli {key}", filetypes=ftypes)
        if path:
            self.file_vars[key].set(path)

    def _start_thread(self):
        # salva configurazione
        self.config["cli_path"] = self.cli_var.get()
        self.config["model"]    = self.model_var.get()
        self.config["files"]    = {k: v.get() for k, v in self.file_vars.items()}
        self._save_config()

        exe   = self.cli_var.get()
        fprog = self.file_vars["prog"].get()
        fdata = self.file_vars["data"].get()
        fopt  = self.file_vars["opt"].get()

        # validazioni
        if not os.path.isfile(exe):
            messagebox.showerror("Errore", "STVP_CmdLine.exe non trovato.")
            return
        for path, key in ((fprog, "prog"), (fdata, "data"), (fopt, "opt")):
            if not os.path.isfile(path) or not self._validate_file(path, key):
                messagebox.showerror("Errore", f"File non valido: {path}")
                return

        # avvia esecuzione
        self.status_var.set("Running…")
        self.btn_start.config(state=tk.DISABLED)
        self.prog_bar.start(10)
        threading.Thread(target=self._program_device, daemon=True).start()

    def _validate_file(self, path, key):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                first = f.readline().strip()
            if key == "prog" and not (first.startswith(":") or first.upper().startswith("S")):
                return False
            if key in ("data", "opt") and not first.startswith(":"):
                return False
            return True
        except Exception:
            return False

    def _build_command(self):
        exe   = self.cli_var.get()
        mdl   = self.model_var.get()
        fprog = self.file_vars["prog"].get()
        fdata = self.file_vars["data"].get()
        fopt  = self.file_vars["opt"].get()

        return [
            exe,
            "-BoardName=ST-LINK",
            "-Port=USB",
            "-ProgMode=SWIM",
            f"-Device={mdl}",
            "-verbose",
            "-no_progOption",
            "-no_loop",
            "-verif",
            f"-FileProg={fprog}",
            f"-FileData={fdata}",
            f"-FileOption={fopt}"
        ]

    def _update_preview(self):
        cmd = self._build_command()
        text = " ".join(cmd)
        self.preview_txt.config(state=tk.NORMAL)
        self.preview_txt.delete("1.0", tk.END)
        self.preview_txt.insert(tk.END, text)
        self.preview_txt.config(state=tk.DISABLED)
        self.after(500, self._update_preview)

    def _log(self, text):
        # log nella box Verbose
        self.verbose_txt.config(state=tk.NORMAL)
        self.verbose_txt.insert(tk.END, text)
        self.verbose_txt.see(tk.END)
        self.verbose_txt.config(state=tk.DISABLED)

        # log nel tab Log
        self.log_txt.config(state=tk.NORMAL)
        self.log_txt.insert(tk.END, text)
        self.log_txt.see(tk.END)
        self.log_txt.config(state=tk.DISABLED)

        # log su file fisico
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(text)

    def _process_log_queue(self):
        try:
            while True:
                msg = self._log_queue.get_nowait()
                self._log(msg)
        except queue.Empty:
            pass
        self.after(100, self._process_log_queue)

    def _program_device(self):
        cmd = self._build_command()
        self._log_queue.put(f"Eseguo: {' '.join(cmd)}\n\n")

        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True
            )
        except Exception as e:
            self._log_queue.put(f"Errore avvio subprocess: {e}\n")
            self._finalize(False)
            return

        for line in proc.stdout:
            self._log_queue.put(line)
        proc.wait()

        success = (proc.returncode == 0)
        if success:
            self._log_queue.put("\n✅ Programmazione completata con successo.\n\n")
        else:
            self._log_queue.put(f"\n❌ Errore di programmazione (codice {proc.returncode}).\n\n")

        self._finalize(success)

    def _finalize(self, success: bool):
        self.prog_bar.stop()
        self.btn_start.config(state=tk.NORMAL)
        self.status_var.set("OK" if success else "KO")


if __name__ == "__main__":
    app = Stm8ProgrammerApp()
    app.mainloop()
