# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src\\app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('trackdb', 'trackdb'),
        ('src\\gt7db\\gt7_car.csv', 'src\\gt7db'),
        ('src\\gt7db\\gt7_layouts.csv', 'src\\gt7db'),
        ('src\\gt7db\\gt7_venues.csv', 'src\\gt7db'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'accelerate',
        'bitsandbytes',
        'datasets',
        'IPython',
        'ipykernel',
        'jupyter',
        'jupyter_client',
        'jupyter_core',
        'keras',
        'matplotlib',
        'notebook',
        'plotly',
        'psycopg',
        'psycopg2',
        'pytest',
        'sqlalchemy',
        'tensorflow',
        'torch',
        'torchaudio',
        'torchvision',
        'transformers',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GT7-Machine-Learning-Tool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='GT7-Machine-Learning-Tool',
)
