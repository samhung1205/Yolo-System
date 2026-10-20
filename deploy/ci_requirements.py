"""Derive CI CPU pins from the verified lab snapshot, without changing runtime pins."""
from pathlib import Path
from export_backend_lock import validated_pins


def cpu_pins(text):
    pins = validated_pins(text)
    result = []
    for pin in pins:
        name, version = pin.split('==')
        if name.lower().startswith(('nvidia-', 'cuda-')) or name.lower() == 'triton':
            continue
        if name.lower() in ('torch', 'torchvision'):
            version = version.split('+')[0] + '+cpu'
        result.append(name + '==' + version)
    return result


if __name__ == '__main__':
    print('\n'.join(cpu_pins(Path(__file__).with_name('backend-linux.lock').read_text())))
