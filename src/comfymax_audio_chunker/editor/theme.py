"""Qt interpretation of ComfyMax's Streamlit dark visual language."""
from PySide6.QtGui import QColor,QFont,QPalette

def apply_theme(window):
    window.setFont(QFont('Segoe UI',10))
    palette=window.palette()
    for role,color in [(QPalette.Window,'#0e1117'),(QPalette.WindowText,'#fafafa'),
                       (QPalette.Base,'#161a23'),(QPalette.AlternateBase,'#1c202b'),
                       (QPalette.Text,'#fafafa'),(QPalette.Button,'#262730'),
                       (QPalette.ButtonText,'#fafafa'),(QPalette.Highlight,'#593039'),
                       (QPalette.HighlightedText,'#ffffff'),(QPalette.ToolTipBase,'#262730'),
                       (QPalette.ToolTipText,'#fafafa')]:
        palette.setColor(role,QColor(color))
    palette.setColor(QPalette.Disabled,QPalette.Text,QColor('#818693'))
    palette.setColor(QPalette.Disabled,QPalette.ButtonText,QColor('#818693'))
    window.setPalette(palette)
    window.setStyleSheet('''
        QMainWindow, QDialog { background: #0e1117; color: #fafafa; }
        QLabel, QCheckBox { color: #e6e8ed; }
        QLabel#projectTitle { font-size: 18px; font-weight: 600; }
        QPushButton { background: #262730; color: #fafafa; border: 1px solid #454955;
                      border-radius: 6px; padding: 7px 10px; min-height: 20px; }
        QPushButton:hover { border-color: #ff4b4b; color: #ff7373; }
        QPushButton:pressed { background: #3e2931; }
        QPushButton#primary { background: #ff4b4b; border-color: #ff4b4b; color: white; }
        QPushButton#primary:hover { background: #e63d46; }
        QPushButton:disabled { background: #1b1e27; color: #818693; border-color: #303440; }
        QComboBox, QDoubleSpinBox, QLineEdit { background: #262730; color: #fafafa;
            border: 1px solid #454955; border-radius: 5px; padding: 5px; min-height: 20px; }
        QComboBox QAbstractItemView { background: #262730; color: #fafafa; selection-background-color: #593039; }
        QTableWidget { background: #161a23; alternate-background-color: #1c202b;
            color: #fafafa; gridline-color: #303440; border: 1px solid #363b48;
            selection-background-color: #593039; selection-color: white; }
        QHeaderView::section { background: #262730; color: #cdd2dc; border: none;
            border-bottom: 1px solid #454955; padding: 7px; }
        QTabWidget::pane { border: 1px solid #363b48; border-radius: 5px; }
        QTabBar::tab { background: #1c202b; color: #b9c0ce; padding: 9px 20px; }
        QTabBar::tab:selected { color: #fafafa; border-bottom: 3px solid #ff4b4b; }
        QSplitter::handle { background: #303440; height: 5px; }
        QSlider::groove:horizontal { background: #363b48; height: 6px; border-radius: 3px; }
        QSlider::handle:horizontal { background: #ff4b4b; width: 16px; margin: -5px 0; border-radius: 7px; }
        QSlider#waveNavigation::groove:horizontal { height: 10px; border-radius: 5px; }
        QSlider#waveNavigation::handle:horizontal { width: 52px; margin: -14px 0;
            background: #8b94a8; border: 1px solid #bac2d0; border-radius: 8px; }
        QSlider#waveNavigation::handle:horizontal:hover { background: #a7b0c3; border-color: #ff4b4b; }
        QSlider#waveNavigation::handle:horizontal:disabled { background: #363b48; border-color: #454955; }
        QToolTip { background: #262730; color: #fafafa; border: 1px solid #454955; }
    ''')
