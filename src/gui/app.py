"""
TraderVolt Migrator - Windows Desktop GUI

A simple wizard-style interface for migrating MT5 data to TraderVolt.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import os
import sys
from pathlib import Path

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv, set_key
load_dotenv()

from src.tradervolt_client.api import TraderVoltClient
from src.gui.commands import run_discovery, run_plan, run_validate, run_apply


class MigratorApp:
    """Main application window with wizard-style navigation."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("TraderVolt Migrator")
        self.root.geometry("900x650")
        self.root.minsize(800, 600)
        
        # Center window on screen
        self.center_window()
        
        # Application state
        self.current_step = 0
        self.migration_files = []
        self.discovery_data = None
        self.plan_data = None
        self.is_authenticated = False
        self.message_queue = queue.Queue()
        
        # Paths
        self.project_root = Path(__file__).parent.parent.parent
        self.env_path = self.project_root / '.env'
        self.migration_dir = self.project_root / 'migration_files'
        self.out_dir = self.project_root / 'out'
        
        # Build UI
        self.setup_styles()
        self.create_widgets()
        self.show_step(0)
        
        # Start message queue processor
        self.process_queue()
    
    def center_window(self):
        """Center the window on screen."""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'+{x}+{y}')
    
    def setup_styles(self):
        """Configure ttk styles for a clean look."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Header style
        style.configure('Header.TLabel', font=('Segoe UI', 16, 'bold'))
        style.configure('SubHeader.TLabel', font=('Segoe UI', 11))
        
        # Step indicator styles
        style.configure('StepActive.TLabel', font=('Segoe UI', 10, 'bold'), foreground='#0078D4')
        style.configure('StepInactive.TLabel', font=('Segoe UI', 10), foreground='#888888')
        style.configure('StepComplete.TLabel', font=('Segoe UI', 10), foreground='#107C10')
        
        # Button styles
        style.configure('Primary.TButton', font=('Segoe UI', 10))
        style.configure('Danger.TButton', font=('Segoe UI', 10))
        
    def create_widgets(self):
        """Create the main UI layout."""
        # Main container
        self.main_frame = ttk.Frame(self.root, padding=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Step indicator at top
        self.create_step_indicator()
        
        # Content area (will hold each step's frame)
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        
        # Navigation buttons at bottom
        self.create_navigation()
        
        # Create all step frames
        self.steps = [
            self.create_step_connect(),
            self.create_step_upload(),
            self.create_step_preview(),
            self.create_step_confirm(),
            self.create_step_progress(),
        ]
    
    def create_step_indicator(self):
        """Create the step progress indicator."""
        indicator_frame = ttk.Frame(self.main_frame)
        indicator_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.step_labels = []
        step_names = ["1. Connect", "2. Upload Files", "3. Preview", "4. Confirm", "5. Migrate"]
        
        for i, name in enumerate(step_names):
            lbl = ttk.Label(indicator_frame, text=name, style='StepInactive.TLabel')
            lbl.pack(side=tk.LEFT, padx=15)
            self.step_labels.append(lbl)
    
    def create_navigation(self):
        """Create navigation buttons."""
        nav_frame = ttk.Frame(self.main_frame)
        nav_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.btn_back = ttk.Button(nav_frame, text="← Back", command=self.prev_step)
        self.btn_back.pack(side=tk.LEFT)
        
        self.btn_next = ttk.Button(nav_frame, text="Next →", command=self.next_step, style='Primary.TButton')
        self.btn_next.pack(side=tk.RIGHT)
    
    # ===== STEP 1: Connect =====
    def create_step_connect(self):
        """Create the connection/authentication step."""
        frame = ttk.Frame(self.content_frame)
        
        ttk.Label(frame, text="Connect to TraderVolt", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Label(frame, text="Enter your TraderVolt API credentials to get started.", 
                  style='SubHeader.TLabel').pack(anchor=tk.W, pady=(5, 20))
        
        # Credentials form
        form_frame = ttk.Frame(frame)
        form_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(form_frame, text="Email:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.entry_email = ttk.Entry(form_frame, width=40)
        self.entry_email.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)
        
        ttk.Label(form_frame, text="Password:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.entry_password = ttk.Entry(form_frame, width=40, show="•")
        self.entry_password.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)
        
        # Load existing credentials
        self.entry_email.insert(0, os.environ.get('TRADERVOLT_EMAIL', ''))
        self.entry_password.insert(0, os.environ.get('TRADERVOLT_PASSWORD', ''))
        
        # Save credentials checkbox
        self.var_save_creds = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, text="Save credentials for next time", 
                        variable=self.var_save_creds).grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)
        
        # Test connection button
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=20)
        
        self.btn_test_conn = ttk.Button(btn_frame, text="Test Connection", command=self.test_connection)
        self.btn_test_conn.pack(side=tk.LEFT)
        
        self.lbl_conn_status = ttk.Label(btn_frame, text="")
        self.lbl_conn_status.pack(side=tk.LEFT, padx=20)
        
        # Discovery section
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=20)
        
        ttk.Label(frame, text="Discovery", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Label(frame, text="Fetch existing data from TraderVolt to compare against your migration files.",
                  style='SubHeader.TLabel').pack(anchor=tk.W, pady=(5, 10))
        
        disc_frame = ttk.Frame(frame)
        disc_frame.pack(fill=tk.X)
        
        self.btn_discover = ttk.Button(disc_frame, text="Run Discovery", command=self.run_discovery_thread, 
                                        state=tk.DISABLED)
        self.btn_discover.pack(side=tk.LEFT)
        
        self.lbl_discovery_status = ttk.Label(disc_frame, text="")
        self.lbl_discovery_status.pack(side=tk.LEFT, padx=20)
        
        return frame
    
    # ===== STEP 2: Upload Files =====
    def create_step_upload(self):
        """Create the file upload step."""
        frame = ttk.Frame(self.content_frame)
        
        ttk.Label(frame, text="Upload Migration Files", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Label(frame, text="Select your MT5 export files (.htm) and symbol configuration (.json).",
                  style='SubHeader.TLabel').pack(anchor=tk.W, pady=(5, 20))
        
        # File list
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.file_listbox = tk.Listbox(list_frame, height=10, font=('Consolas', 10))
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        self.file_listbox.configure(yscrollcommand=scrollbar.set)
        
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="Add Files...", command=self.add_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Remove Selected", command=self.remove_selected_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Clear All", command=self.clear_files).pack(side=tk.LEFT, padx=5)
        
        # Auto-detect existing files
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)
        
        detect_frame = ttk.Frame(frame)
        detect_frame.pack(fill=tk.X)
        
        ttk.Button(detect_frame, text="Auto-detect from migration_files/", 
                   command=self.auto_detect_files).pack(side=tk.LEFT)
        
        self.lbl_file_status = ttk.Label(detect_frame, text="")
        self.lbl_file_status.pack(side=tk.LEFT, padx=20)
        
        return frame
    
    # ===== STEP 3: Preview =====
    def create_step_preview(self):
        """Create the preview/plan step."""
        frame = ttk.Frame(self.content_frame)
        
        ttk.Label(frame, text="Preview Migration Plan", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Label(frame, text="Review what will be created in TraderVolt before proceeding.",
                  style='SubHeader.TLabel').pack(anchor=tk.W, pady=(5, 20))
        
        # Generate plan button
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        
        self.btn_generate_plan = ttk.Button(btn_frame, text="Generate Plan", command=self.generate_plan_thread)
        self.btn_generate_plan.pack(side=tk.LEFT)
        
        self.lbl_plan_status = ttk.Label(btn_frame, text="")
        self.lbl_plan_status.pack(side=tk.LEFT, padx=20)
        
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)
        
        # Summary treeview with expandable rows
        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ('entity_type', 'source_count', 'existing', 'to_create', 'skipped')
        self.plan_tree = ttk.Treeview(tree_frame, columns=columns, show='tree headings', height=8)
        
        self.plan_tree.heading('#0', text='▶')
        self.plan_tree.heading('entity_type', text='Entity Type')
        self.plan_tree.heading('source_count', text='In Source')
        self.plan_tree.heading('existing', text='Already Exists')
        self.plan_tree.heading('to_create', text='To Create')
        self.plan_tree.heading('skipped', text='Skipped')
        
        self.plan_tree.column('#0', width=30, stretch=False)
        self.plan_tree.column('entity_type', width=150)
        self.plan_tree.column('source_count', width=100, anchor=tk.CENTER)
        self.plan_tree.column('existing', width=120, anchor=tk.CENTER)
        self.plan_tree.column('to_create', width=100, anchor=tk.CENTER)
        self.plan_tree.column('skipped', width=100, anchor=tk.CENTER)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.plan_tree.yview)
        self.plan_tree.configure(yscrollcommand=scrollbar.set)
        
        self.plan_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click to show details
        self.plan_tree.bind('<Double-Button-1>', self.on_tree_double_click)
        
        # Warnings area
        ttk.Label(frame, text="Warnings:", font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W, pady=(10, 5))
        
        self.txt_warnings = scrolledtext.ScrolledText(frame, height=5, font=('Consolas', 9), state=tk.DISABLED)
        self.txt_warnings.pack(fill=tk.X)
        
        return frame
    
    # ===== STEP 4: Confirm =====
    def create_step_confirm(self):
        """Create the confirmation step."""
        frame = ttk.Frame(self.content_frame)
        
        ttk.Label(frame, text="⚠️ Confirm Migration", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Label(frame, text="Please review carefully before proceeding. This action will create entities in TraderVolt.",
                  style='SubHeader.TLabel').pack(anchor=tk.W, pady=(5, 20))
        
        # Summary box
        summary_frame = ttk.LabelFrame(frame, text="Migration Summary", padding=15)
        summary_frame.pack(fill=tk.X, pady=10)
        
        self.lbl_summary = ttk.Label(summary_frame, text="No plan generated yet.", wraplength=700, justify=tk.LEFT)
        self.lbl_summary.pack(anchor=tk.W)
        
        # Test mode option
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)
        
        mode_frame = ttk.LabelFrame(frame, text="Migration Mode", padding=15)
        mode_frame.pack(fill=tk.X, pady=10)
        
        self.var_test_mode = tk.BooleanVar(value=True)
        ttk.Radiobutton(mode_frame, text="🧪 TEST MODE - Create with MIG_TEST_ prefix (recommended for first run)", 
                        variable=self.var_test_mode, value=True).pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(mode_frame, text="🚀 PRODUCTION MODE - Create real entities", 
                        variable=self.var_test_mode, value=False).pack(anchor=tk.W, pady=2)
        
        # Confirmation
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)
        
        confirm_frame = ttk.Frame(frame)
        confirm_frame.pack(fill=tk.X, pady=10)
        
        self.var_confirmed = tk.BooleanVar(value=False)
        self.chk_confirm = ttk.Checkbutton(confirm_frame, text="I have reviewed the plan and understand the changes", 
                                            variable=self.var_confirmed, command=self.update_confirm_state)
        self.chk_confirm.pack(anchor=tk.W)
        
        ttk.Label(confirm_frame, text="Type MIGRATE to confirm:").pack(anchor=tk.W, pady=(15, 5))
        self.entry_confirm = ttk.Entry(confirm_frame, width=20)
        self.entry_confirm.pack(anchor=tk.W)
        self.entry_confirm.bind('<KeyRelease>', lambda e: self.update_confirm_state())
        
        return frame
    
    # ===== STEP 5: Progress =====
    def create_step_progress(self):
        """Create the progress/results step."""
        frame = ttk.Frame(self.content_frame)
        
        ttk.Label(frame, text="Migration Progress", style='Header.TLabel').pack(anchor=tk.W)
        self.lbl_progress_status = ttk.Label(frame, text="Ready to start migration.", style='SubHeader.TLabel')
        self.lbl_progress_status.pack(anchor=tk.W, pady=(5, 20))
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(frame, variable=self.progress_var, maximum=100, length=400)
        self.progress_bar.pack(fill=tk.X, pady=10)
        
        self.lbl_progress_detail = ttk.Label(frame, text="")
        self.lbl_progress_detail.pack(anchor=tk.W)
        
        # Log output
        ttk.Label(frame, text="Log:", font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W, pady=(20, 5))
        
        self.txt_log = scrolledtext.ScrolledText(frame, height=15, font=('Consolas', 9), state=tk.DISABLED)
        self.txt_log.pack(fill=tk.BOTH, expand=True)
        
        # Start button (hidden until ready)
        self.btn_start_migration = ttk.Button(frame, text="▶ Start Migration", command=self.start_migration_thread,
                                               style='Primary.TButton')
        self.btn_start_migration.pack(pady=15)
        
        return frame
    
    # ===== Navigation =====
    def show_step(self, step_index):
        """Show the specified step and hide others."""
        # Hide all frames
        for f in self.steps:
            f.pack_forget()
        
        # Show current step
        self.steps[step_index].pack(fill=tk.BOTH, expand=True)
        self.current_step = step_index
        
        # Update step indicators
        for i, lbl in enumerate(self.step_labels):
            if i < step_index:
                lbl.configure(style='StepComplete.TLabel', text="✓ " + lbl.cget('text').split('. ', 1)[-1])
            elif i == step_index:
                lbl.configure(style='StepActive.TLabel')
            else:
                lbl.configure(style='StepInactive.TLabel')
        
        # Update navigation buttons
        self.btn_back.configure(state=tk.NORMAL if step_index > 0 else tk.DISABLED)
        
        if step_index == 4:  # Progress step
            self.btn_next.configure(text="Close", command=self.root.quit)
        else:
            self.btn_next.configure(text="Next →", command=self.next_step)
    
    def next_step(self):
        """Advance to the next step with validation."""
        if self.current_step == 0:  # Connect
            if not self.is_authenticated:
                messagebox.showwarning("Not Connected", "Please test your connection before proceeding.")
                return
            if not self.discovery_data:
                if not messagebox.askyesno("Skip Discovery?", 
                    "Discovery has not been run. Continue without discovery data?\n\n"
                    "Note: Discovery helps identify existing entities to avoid duplicates."):
                    return
        
        elif self.current_step == 1:  # Upload
            if not self.migration_files:
                messagebox.showwarning("No Files", "Please add at least one migration file.")
                return
        
        elif self.current_step == 2:  # Preview
            if not self.plan_data:
                messagebox.showwarning("No Plan", "Please generate a migration plan first.")
                return
        
        elif self.current_step == 3:  # Confirm
            if not self.var_confirmed.get():
                messagebox.showwarning("Not Confirmed", "Please check the confirmation box.")
                return
            if self.entry_confirm.get().upper() != "MIGRATE":
                messagebox.showwarning("Not Confirmed", "Please type MIGRATE to confirm.")
                return
        
        if self.current_step < len(self.steps) - 1:
            self.show_step(self.current_step + 1)
    
    def prev_step(self):
        """Go back to the previous step."""
        if self.current_step > 0:
            self.show_step(self.current_step - 1)
    
    # ===== Actions =====
    def test_connection(self):
        """Test TraderVolt API connection."""
        email = self.entry_email.get().strip()
        password = self.entry_password.get().strip()
        
        if not email or not password:
            messagebox.showwarning("Missing Credentials", "Please enter both email and password.")
            return
        
        # Set environment variables
        os.environ['TRADERVOLT_EMAIL'] = email
        os.environ['TRADERVOLT_PASSWORD'] = password
        
        # Save to .env if requested
        if self.var_save_creds.get():
            set_key(str(self.env_path), 'TRADERVOLT_EMAIL', email)
            set_key(str(self.env_path), 'TRADERVOLT_PASSWORD', password)
        
        self.btn_test_conn.configure(state=tk.DISABLED)
        self.lbl_conn_status.configure(text="Connecting...", foreground='#666666')
        self.root.update()
        
        def test():
            try:
                # Clear any cached tokens to force fresh login
                from pathlib import Path
                token_cache = Path(__file__).parent.parent.parent / 'out' / 'token.json'
                if token_cache.exists():
                    token_cache.unlink()
                
                client = TraderVoltClient()
                # Explicitly attempt authentication
                if client.token_manager.ensure_authenticated():
                    self.message_queue.put(('conn_success', None))
                else:
                    self.message_queue.put(('conn_fail', 'Authentication failed - check credentials'))
            except Exception as e:
                self.message_queue.put(('conn_fail', str(e)))
        
        threading.Thread(target=test, daemon=True).start()
    
    def run_discovery_thread(self):
        """Run discovery in a background thread."""
        self.btn_discover.configure(state=tk.DISABLED)
        self.lbl_discovery_status.configure(text="Running discovery...", foreground='#666666')
        self.root.update()
        
        def discover():
            try:
                # Run discovery command
                result = run_discovery(callback=lambda msg: self.message_queue.put(('log', msg)))
                self.message_queue.put(('discovery_complete', result))
            except Exception as e:
                self.message_queue.put(('discovery_fail', str(e)))
        
        threading.Thread(target=discover, daemon=True).start()
    
    def add_files(self):
        """Open file dialog to add migration files."""
        files = filedialog.askopenfilenames(
            title="Select Migration Files",
            filetypes=[
                ("MT5 Exports", "*.htm *.html *.json"),
                ("HTML Files", "*.htm *.html"),
                ("JSON Files", "*.json"),
                ("All Files", "*.*")
            ]
        )
        for f in files:
            if f not in self.migration_files:
                self.migration_files.append(f)
                self.file_listbox.insert(tk.END, f)
        self.update_file_status()
    
    def remove_selected_file(self):
        """Remove selected file from list."""
        selection = self.file_listbox.curselection()
        if selection:
            idx = selection[0]
            self.file_listbox.delete(idx)
            del self.migration_files[idx]
        self.update_file_status()
    
    def clear_files(self):
        """Clear all files from list."""
        self.file_listbox.delete(0, tk.END)
        self.migration_files.clear()
        self.update_file_status()
    
    def auto_detect_files(self):
        """Auto-detect files in migration_files directory."""
        if not self.migration_dir.exists():
            messagebox.showinfo("Not Found", f"Directory not found: {self.migration_dir}")
            return
        
        patterns = ['*.htm', '*.html', '*.json']
        found = []
        for pattern in patterns:
            found.extend(self.migration_dir.glob(pattern))
        
        self.clear_files()
        for f in sorted(found):
            self.migration_files.append(str(f))
            self.file_listbox.insert(tk.END, str(f))
        
        self.lbl_file_status.configure(text=f"Found {len(found)} files", foreground='#107C10')
    
    def update_file_status(self):
        """Update the file count status."""
        count = len(self.migration_files)
        self.lbl_file_status.configure(text=f"{count} file(s) selected")
    
    def generate_plan_thread(self):
        """Generate migration plan in background thread."""
        self.btn_generate_plan.configure(state=tk.DISABLED)
        self.lbl_plan_status.configure(text="Generating plan...", foreground='#666666')
        
        # Clear existing plan data
        for item in self.plan_tree.get_children():
            self.plan_tree.delete(item)
        
        def generate():
            try:
                source_dir = str(self.migration_dir)
                result = run_plan(source_dir=source_dir, callback=lambda msg: self.message_queue.put(('log', msg)))
                self.message_queue.put(('plan_complete', result))
            except Exception as e:
                self.message_queue.put(('plan_fail', str(e)))
        
        threading.Thread(target=generate, daemon=True).start()
    
    def update_confirm_state(self):
        """Update confirmation state based on inputs."""
        confirmed = self.var_confirmed.get() and self.entry_confirm.get().upper() == "MIGRATE"
        # This could enable/disable the next button if needed
    
    def start_migration_thread(self):
        """Start the migration in a background thread."""
        self.btn_start_migration.configure(state=tk.DISABLED)
        self.progress_var.set(0)
        self.lbl_progress_status.configure(text="Migration in progress...")
        
        # Clear log
        self.txt_log.configure(state=tk.NORMAL)
        self.txt_log.delete(1.0, tk.END)
        self.txt_log.configure(state=tk.DISABLED)
        
        test_mode = self.var_test_mode.get()
        
        def migrate():
            try:
                def progress_callback(msg, progress=None):
                    self.message_queue.put(('migration_log', msg))
                    if progress is not None:
                        self.message_queue.put(('migration_progress', progress))
                
                result = run_apply(
                    test_mode=test_mode,
                    confirm=True,
                    callback=progress_callback
                )
                self.message_queue.put(('migration_complete', result))
            except Exception as e:
                self.message_queue.put(('migration_fail', str(e)))
        
        threading.Thread(target=migrate, daemon=True).start()
    
    def log_message(self, message):
        """Append a message to the log text widget."""
        self.txt_log.configure(state=tk.NORMAL)
        self.txt_log.insert(tk.END, message + "\n")
        self.txt_log.see(tk.END)
        self.txt_log.configure(state=tk.DISABLED)
    
    def process_queue(self):
        """Process messages from background threads."""
        try:
            while True:
                msg_type, data = self.message_queue.get_nowait()
                
                if msg_type == 'conn_success':
                    self.is_authenticated = True
                    self.lbl_conn_status.configure(text="✓ Connected successfully!", foreground='#107C10')
                    self.btn_test_conn.configure(state=tk.NORMAL)
                    self.btn_discover.configure(state=tk.NORMAL)
                
                elif msg_type == 'conn_fail':
                    self.is_authenticated = False
                    self.lbl_conn_status.configure(text=f"✗ Connection failed: {data}", foreground='#D13438')
                    self.btn_test_conn.configure(state=tk.NORMAL)
                
                elif msg_type == 'discovery_complete':
                    self.discovery_data = data
                    self.lbl_discovery_status.configure(text="✓ Discovery complete!", foreground='#107C10')
                    self.btn_discover.configure(state=tk.NORMAL)
                
                elif msg_type == 'discovery_fail':
                    self.lbl_discovery_status.configure(text=f"✗ Discovery failed: {data}", foreground='#D13438')
                    self.btn_discover.configure(state=tk.NORMAL)
                
                elif msg_type == 'plan_complete':
                    self.plan_data = data
                    self.lbl_plan_status.configure(text="✓ Plan generated!", foreground='#107C10')
                    self.btn_generate_plan.configure(state=tk.NORMAL)
                    self.update_plan_display()
                
                elif msg_type == 'plan_fail':
                    self.lbl_plan_status.configure(text=f"✗ Plan failed: {data}", foreground='#D13438')
                    self.btn_generate_plan.configure(state=tk.NORMAL)
                
                elif msg_type == 'migration_log':
                    self.log_message(data)
                
                elif msg_type == 'migration_progress':
                    self.progress_var.set(data)
                    self.lbl_progress_detail.configure(text=f"{data:.0f}% complete")
                
                elif msg_type == 'migration_complete':
                    self.progress_var.set(100)
                    self.lbl_progress_status.configure(text="✓ Migration complete!")
                    self.lbl_progress_detail.configure(text="100% complete")
                    self.log_message("\n=== MIGRATION COMPLETE ===")
                    messagebox.showinfo("Complete", "Migration completed successfully!")
                
                elif msg_type == 'migration_fail':
                    self.lbl_progress_status.configure(text=f"✗ Migration failed: {data}")
                    self.log_message(f"\n=== ERROR: {data} ===")
                    self.btn_start_migration.configure(state=tk.NORMAL)
                
                elif msg_type == 'log':
                    self.log_message(data)
                    
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(100, self.process_queue)
    
    def update_plan_display(self):
        """Update the plan preview display."""
        if not self.plan_data:
            return
        
        # Clear tree
        for item in self.plan_tree.get_children():
            self.plan_tree.delete(item)
        
        # Load plan file if plan_data is a path
        plan_path = self.out_dir / 'migration_plan.json'
        if plan_path.exists():
            import json
            with open(plan_path, 'r') as f:
                plan = json.load(f)
            
            # Store plan for detail view
            self.current_plan = plan
            
            # Populate tree with comparison data and entities
            if 'comparison' in plan:
                entities = plan.get('entities', {})
                
                for entity_type, counts in plan['comparison'].items():
                    # Insert parent row
                    parent = self.plan_tree.insert('', tk.END, text='', values=(
                        entity_type,
                        counts.get('source', 0),
                        counts.get('existing', 0),
                        counts.get('to_create', 0),
                        counts.get('skipped', 0)
                    ), tags=('parent',))
                    
                    # Add child rows with entity details (collapsed by default)
                    entity_list = entities.get(entity_type, [])
                    if entity_list:
                        # Limit to first 5 for preview, add "..." if more
                        display_count = min(5, len(entity_list))
                        for i, entity in enumerate(entity_list[:display_count]):
                            # Get key identifying field
                            display_name = (
                                entity.get('name') or 
                                entity.get('email') or 
                                entity.get('Symbol') or
                                entity.get('login') or
                                f"Entity {i+1}"
                            )
                            
                            # Show key fields in columns
                            detail_text = self._format_entity_preview(entity, entity_type)
                            
                            self.plan_tree.insert(parent, tk.END, text='', values=(
                                f"  {display_name}",
                                detail_text,
                                '', '', ''
                            ), tags=('child',))
                        
                        if len(entity_list) > display_count:
                            self.plan_tree.insert(parent, tk.END, text='', values=(
                                f"  ... and {len(entity_list) - display_count} more",
                                '', '', '', ''
                            ), tags=('child',))
            
            # Update summary label
            total_create = sum(c.get('to_create', 0) for c in plan.get('comparison', {}).values())
            self.lbl_summary.configure(text=f"Total entities to create: {total_create}")
            
            # Show warnings
            self.txt_warnings.configure(state=tk.NORMAL)
            self.txt_warnings.delete(1.0, tk.END)
            warnings = plan.get('warnings', [])
            if warnings:
                self.txt_warnings.insert(tk.END, "\n".join(warnings))
            else:
                self.txt_warnings.insert(tk.END, "No warnings.")
            self.txt_warnings.configure(state=tk.DISABLED)
    
    def _format_entity_preview(self, entity, entity_type):
        """Format entity data for preview display."""
        if entity_type == 'symbols':
            desc = entity.get('Description', entity.get('description', ''))
            return desc[:40] + '...' if len(desc) > 40 else desc
        elif entity_type == 'traders':
            parts = []
            if entity.get('firstName'):
                parts.append(entity['firstName'])
            if entity.get('lastName'):
                parts.append(entity['lastName'])
            if entity.get('email'):
                parts.append(f"({entity['email']})")
            return ' '.join(parts)[:60]
        elif entity_type == 'orders':
            symbol = entity.get('symbol', '?')
            volume = entity.get('volume', 0)
            return f"{symbol} | Vol: {volume}"
        elif entity_type == 'positions':
            symbol = entity.get('symbol', '?')
            volume = entity.get('volume', 0)
            return f"{symbol} | Vol: {volume}"
        else:
            return ''
    
    def on_tree_double_click(self, event):
        """Handle double-click on tree item to show full details."""
        item = self.plan_tree.selection()
        if not item:
            return
        
        # Get the item's values
        values = self.plan_tree.item(item[0], 'values')
        if not values:
            return
        
        entity_type = values[0].strip()
        
        # If it's a parent row with entities, show detail window
        if hasattr(self, 'current_plan') and entity_type in self.current_plan.get('entities', {}):
            self.show_entity_details(entity_type)
    
    def show_entity_details(self, entity_type):
        """Show a popup window with full entity details."""
        entities = self.current_plan.get('entities', {}).get(entity_type, [])
        if not entities:
            return
        
        # Create popup window
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"{entity_type} - Details ({len(entities)} items)")
        detail_window.geometry("800x600")
        
        # Header
        header = ttk.Label(detail_window, text=f"{entity_type.upper()} ({len(entities)} total)", 
                          font=('Segoe UI', 12, 'bold'))
        header.pack(pady=10)
        
        # Scrollable text area
        text_frame = ttk.Frame(detail_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        txt = scrolledtext.ScrolledText(text_frame, font=('Consolas', 9), wrap=tk.WORD)
        txt.pack(fill=tk.BOTH, expand=True)
        
        # Display entities
        import json
        for i, entity in enumerate(entities, 1):
            txt.insert(tk.END, f"{'='*70}\n")
            txt.insert(tk.END, f"Item {i}/{len(entities)}\n")
            txt.insert(tk.END, f"{'='*70}\n")
            
            # Format nicely based on entity type
            if entity_type == 'symbols':
                txt.insert(tk.END, f"Symbol: {entity.get('name', 'N/A')}\n")
                txt.insert(tk.END, f"Description: {entity.get('Description', entity.get('description', 'N/A'))}\n")
                txt.insert(tk.END, f"Group: {entity.get('symbolsGroupId', 'N/A')}\n")
                txt.insert(tk.END, f"Digits: {entity.get('Digits', entity.get('digits', 'N/A'))}\n")
            elif entity_type == 'traders':
                txt.insert(tk.END, f"Name: {entity.get('firstName', '')} {entity.get('lastName', '')}\n")
                txt.insert(tk.END, f"Email: {entity.get('email', 'N/A')}\n")
                txt.insert(tk.END, f"Login: {entity.get('login', 'N/A')}\n")
                txt.insert(tk.END, f"Group: {entity.get('tradersGroupId', 'N/A')}\n")
                txt.insert(tk.END, f"Leverage: {entity.get('leverage', 'N/A')}\n")
            else:
                # Generic JSON display
                txt.insert(tk.END, json.dumps(entity, indent=2))
            
            txt.insert(tk.END, "\n\n")
        
        txt.configure(state=tk.DISABLED)
        
        # Close button
        btn_close = ttk.Button(detail_window, text="Close", command=detail_window.destroy)
        btn_close.pack(pady=10)


def main():
    """Launch the application."""
    root = tk.Tk()
    app = MigratorApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
