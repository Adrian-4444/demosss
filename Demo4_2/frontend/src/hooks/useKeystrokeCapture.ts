import { useState, useRef, useCallback } from "react";

export interface KeystrokeFeatures {
    hold_times: number[];
    flight_times: number[];
    latencies: number[];
    typing_speed: number;
    backspace_count: number;
    error_rate: number;
}

interface KeyTimePoint {
    key: string;
    downTime: number;
    upTime: number | null;
}

export function useKeystrokeCapture() {
    const [backspaceCount, setBackspaceCount] = useState(0);
    const typedBufferRef = useRef<KeyTimePoint[]>([]);
    const totalKeysPressedRef = useRef(0);

    const resetKeystrokes = useCallback(() => {
        typedBufferRef.current = [];
        setBackspaceCount(0);
        totalKeysPressedRef.current = 0;
    }, []);

    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
        // Ignore modifier keys like Shift, Control, Alt, Meta if they don't produce characters
        if (["Control", "Alt", "Meta", "Shift", "CapsLock", "Tab", "Enter", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) {
            return;
        }

        totalKeysPressedRef.current += 1;
        const now = performance.now();

        if (e.key === "Backspace") {
            setBackspaceCount(prev => prev + 1);
            if (typedBufferRef.current.length > 0) {
                // Pop the last keypress timing from stack on backspace
                typedBufferRef.current.pop();
            }
        } else {
            // Push new keypress timing onto stack
            typedBufferRef.current.push({
                key: e.key,
                downTime: now,
                upTime: null
            });
        }
    }, []);

    const handleKeyUp = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
        if (["Control", "Alt", "Meta", "Shift", "CapsLock", "Tab", "Enter"].includes(e.key) || e.key === "Backspace") {
            return;
        }

        const now = performance.now();
        
        // Find the last key of this character that hasn't been released yet
        const buffer = typedBufferRef.current;
        for (let i = buffer.length - 1; i >= 0; i--) {
            if (buffer[i].key === e.key && buffer[i].upTime === null) {
                buffer[i].upTime = now;
                break;
            }
        }
    }, []);

    const getKeystrokeFeatures = useCallback((): KeystrokeFeatures | null => {
        const buffer = typedBufferRef.current;
        const L = buffer.length;

        if (L < 4) {
            return null; // Too short to extract timing biometrics reliably
        }

        // Fill any unreleased keyup times with a default hold time (e.g. 100ms) to prevent null values
        const cleanBuffer = buffer.map(item => ({
            ...item,
            upTime: item.upTime !== null ? item.upTime : item.downTime + 100.0
        }));

        const hold_times: number[] = [];
        const flight_times: number[] = [];
        const latencies: number[] = [];

        // 1. Calculate hold times
        for (let i = 0; i < L; i++) {
            hold_times.push(cleanBuffer[i].upTime - cleanBuffer[i].downTime);
        }

        // 2. Calculate flight times and press-to-press latencies
        for (let i = 0; i < L - 1; i++) {
            flight_times.push(cleanBuffer[i+1].downTime - cleanBuffer[i].upTime);
            latencies.push(cleanBuffer[i+1].downTime - cleanBuffer[i].downTime);
        }

        // 3. Compute typing speed (keys per second)
        const totalDurationMs = cleanBuffer[L - 1].downTime - cleanBuffer[0].downTime;
        const typing_speed = totalDurationMs > 0 ? (L / (totalDurationMs / 1000)) : 5.0;

        // 4. Compute error rate (backspaces divided by total physical keys pressed)
        const error_rate = totalKeysPressedRef.current > 0 ? (backspaceCount / totalKeysPressedRef.current) : 0.0;

        return {
            hold_times: hold_times.map(h => parseFloat(h.toFixed(1))),
            flight_times: flight_times.map(f => parseFloat(f.toFixed(1))),
            latencies: latencies.map(l => parseFloat(l.toFixed(1))),
            typing_speed: parseFloat(typing_speed.toFixed(2)),
            backspace_count: backspaceCount,
            error_rate: parseFloat(error_rate.toFixed(3))
        };
    }, [backspaceCount]);

    return {
        backspaceCount,
        handleKeyDown,
        handleKeyUp,
        resetKeystrokes,
        getKeystrokeFeatures
    };
}
