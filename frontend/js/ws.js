export function connectLive({onEvent,onStatus}){
  let socket,timer,delay=1000,stopped=false,watchdog,last=Date.now();
  const connect=()=>{if(stopped)return;socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws/live`);
    socket.onopen=()=>{delay=1000;last=Date.now();onStatus(true);};
    socket.onmessage=e=>{last=Date.now();try{const event=JSON.parse(e.data);if(event.type!=='heartbeat')onEvent(event);}catch(error){console.warn('Invalid live event',error);}};
    socket.onerror=()=>socket.close();
    socket.onclose=()=>{onStatus(false);if(!stopped){timer=setTimeout(connect,delay);delay=Math.min(30000,delay*2);}};
  };
  connect();watchdog=setInterval(()=>{if(socket?.readyState===1&&Date.now()-last>35000)socket.close();},5000);
  return()=>{stopped=true;clearTimeout(timer);clearInterval(watchdog);socket?.close();};
}
