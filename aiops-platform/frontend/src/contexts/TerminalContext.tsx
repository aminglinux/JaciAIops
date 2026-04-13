import React, { createContext, useContext, useRef, useState, useCallback, useEffect } from 'react';
import { Terminal as XTerminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';

interface TerminalContextType {
  connected: boolean;
  connecting: boolean;
  ws: WebSocket | null;
  terminal: XTerminal | null;
  fitAddon: FitAddon | null;
  connect: () => void;
  disconnect: () => void;
  sendCommand: (command: string) => void;
  registerTerminal: (terminal: XTerminal, fitAddon: FitAddon) => void;
  unregisterTerminal: () => void;
}

const TerminalContext = createContext<TerminalContextType | null>(null);

const IDLE_TIMEOUT = 10 * 60 * 1000;

export const TerminalProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const wsRef = useRef<WebSocket | null>(null);
  const terminalRef = useRef<XTerminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);
  
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);

  const resetIdleTimer = useCallback(() => {
    if (idleTimerRef.current) {
      clearTimeout(idleTimerRef.current);
    }
    
    if (connected) {
      idleTimerRef.current = setTimeout(() => {
        console.log('[Terminal] Idle timeout, disconnecting...');
        disconnect();
      }, IDLE_TIMEOUT);
    }
  }, [connected]);

  const connect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    setConnecting(true);
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/terminal`;

    console.log('[Terminal] Connecting to', wsUrl);

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[Terminal] Connected');
      setConnected(true);
      setConnecting(false);
      reconnectAttemptsRef.current = 0;
      resetIdleTimer();
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        
        if (msg.type === 'output') {
          terminalRef.current?.write(msg.data);
        } else if (msg.type === 'error') {
          terminalRef.current?.writeln(`\x1b[1;31mError: ${msg.data}\x1b[0m`);
        }
        
        resetIdleTimer();
      } catch (e) {
        console.error('[Terminal] Failed to parse message:', e);
      }
    };

    ws.onerror = () => {
      console.log('[Terminal] Connection error');
      terminalRef.current?.writeln('\x1b[1;31mConnection error\x1b[0m');
      setConnected(false);
      setConnecting(false);
    };

    ws.onclose = () => {
      console.log('[Terminal] Connection closed');
      terminalRef.current?.writeln('\x1b[1;33mConnection closed\x1b[0m');
      setConnected(false);
      setConnecting(false);
    };
  }, [resetIdleTimer]);

  const disconnect = useCallback(() => {
    if (idleTimerRef.current) {
      clearTimeout(idleTimerRef.current);
      idleTimerRef.current = null;
    }
    
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
    setConnected(false);
    setConnecting(false);
  }, []);

  const sendCommand = useCallback((command: string) => {
    if (wsRef.current && connected) {
      wsRef.current.send(JSON.stringify({ type: 'input', data: command }));
      resetIdleTimer();
    }
  }, [connected, resetIdleTimer]);

  const registerTerminal = useCallback((terminal: XTerminal, fitAddon: FitAddon) => {
    terminalRef.current = terminal;
    fitAddonRef.current = fitAddon;

    terminal.onData((data) => {
      if (wsRef.current && connected) {
        wsRef.current.send(JSON.stringify({ type: 'input', data }));
        resetIdleTimer();
      }
    });
  }, [connected, resetIdleTimer]);

  const unregisterTerminal = useCallback(() => {
    terminalRef.current = null;
    fitAddonRef.current = null;
  }, []);

  useEffect(() => {
    return () => {
      if (idleTimerRef.current) {
        clearTimeout(idleTimerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    const handleResize = () => {
      if (fitAddonRef.current && terminalRef.current) {
        fitAddonRef.current.fit();
        
        if (wsRef.current && connected) {
          const dims = fitAddonRef.current.proposeDimensions();
          if (dims) {
            wsRef.current.send(JSON.stringify({
              type: 'resize',
              rows: dims.rows,
              cols: dims.cols,
            }));
          }
        }
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [connected]);

  return (
    <TerminalContext.Provider
      value={{
        connected,
        connecting,
        ws: wsRef.current,
        terminal: terminalRef.current,
        fitAddon: fitAddonRef.current,
        connect,
        disconnect,
        sendCommand,
        registerTerminal,
        unregisterTerminal,
      }}
    >
      {children}
    </TerminalContext.Provider>
  );
};

export const useTerminal = () => {
  const context = useContext(TerminalContext);
  if (!context) {
    throw new Error('useTerminal must be used within a TerminalProvider');
  }
  return context;
};
