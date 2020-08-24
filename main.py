# -*- coding: utf-8 -*-
import logging
import multiprocessing
import time
from multiprocessing.queues import Queue

import pyaudio as pa
from websocket import ABNF


def websocket_worker(q: Queue):
    import websocket
    try:
        import thread
    except ImportError:
        import _thread as thread

    def on_message(ws, message):
        print(message)

    def on_error(ws, error):
        print(error)

    def on_close(ws):
        print("### closed ###")

    def on_open(ws):
        def run(*args):
            while True:
                try:
                    in_data = q.get()
                    # send binary, default is Text
                    ws.send(in_data, opcode=ABNF.OPCODE_BINARY)
                except Exception as e:
                    print(e)
                    logging.exception(e)
                    ws.close()
                    print("thread terminating...")
                    break

        thread.start_new_thread(run, ())

    websocket.enableTrace(False)  # for debug
    ws = websocket.WebSocketApp("ws://172.20.121.19:8000/uid/1/ws?token=123",
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.run_forever()


if __name__ == '__main__':

    SAMPLE_RATE = 16000
    # duration of signal frame, seconds
    FRAME_LEN = 0.02
    # number of audio channels (expect mono signal)
    CHANNELS = 1

    CHUNK_SIZE = int(FRAME_LEN * SAMPLE_RATE)

    format = "%(asctime)s: %(message)s"
    logging.basicConfig(format=format, level=logging.DEBUG,
                        datefmt="%H:%M:%S")

    ctx = multiprocessing.get_context()
    q = ctx.Queue()
    process = ctx.Process(target=websocket_worker, args=(q,))
    process.start()

    p = pa.PyAudio()
    print('Available audio input devices:')
    input_devices = []
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev.get('maxInputChannels'):
            input_devices.append(i)
            print(i, dev.get('name'))

    if len(input_devices):
        dev_idx = 1
        print('Default input device ID {}'.format(dev_idx))
        while dev_idx not in input_devices:
            print('Please type input device ID:')
            dev_idx = int(input())


        def callback(in_data, frame_count, time_info, status):
            # print('callback time {}'.format(time.time()))
            q.put(in_data)
            return (in_data, pa.paContinue)


        stream = p.open(format=pa.paInt16,
                        channels=CHANNELS,
                        rate=SAMPLE_RATE,
                        input=True,
                        input_device_index=dev_idx,
                        stream_callback=callback,
                        frames_per_buffer=CHUNK_SIZE)

        print('Listening...')

        stream.start_stream()

        while stream.is_active():
            time.sleep(0.1)
    else:
        print('ERROR: No audio input device found.')

    stream.stop_stream()
    stream.close()
    p.terminate()

    # Wait for the worker to finish
    q.close()
    q.join_thread()
    process.join()
