/** One in-flight, retryable battle chunk. Only the server acknowledges progress. */
export class BattleSession {
  constructor(request){this.request=request;this.begin({});}
  begin({runId=null,context=null,sequence=0,verifiedTick=0,resumeToken=null}={}){
    this.runId=runId;this.context=context;this.sequence=sequence;this.verifiedTick=verifiedTick;this.resumeToken=resumeToken;
    this.actions=[];this.pending=null;this.inFlight=null;this.finished=null;
  }
  get modern(){return this.context?.rulesVersion===2;}
  get busy(){return Boolean(this.inFlight);}
  async flush(endTick,{finish=false}={}){
    if(this.finished)return this.finished;
    if(this.inFlight){await this.inFlight;if(this.finished)return this.finished;}
    if(!this.pending){
      if(!finish&&endTick===this.verifiedTick&&!this.actions.length)return null;
      this.pending={finish,count:this.actions.length,payload:{runId:this.runId,sequence:this.sequence+1,endTick,actions:this.actions.map(action=>({...action}))}};
      if(this.resumeToken)this.pending.payload.resumeToken=this.resumeToken;
    }
    const pending=this.pending;
    this.inFlight=(async()=>{
      const result=await this.request(pending.finish?'/api/run/finish':'/api/run/checkpoint',pending.payload);
      if(result.poolClosed===true&&result.ended===true&&result.result&&result.reward){
        // A closed pool can bank only its last trusted checkpoint. Pending
        // local ticks have no financial effect and must not be shown as saved.
        this.sequence=result.sequence;this.verifiedTick=result.verifiedTick;
        this.actions.splice(0);this.pending=null;this.finished=result;return result;
      }
      if(result.sequence!==pending.payload.sequence || result.verifiedTick!==pending.payload.endTick)throw new Error('The battle acknowledgement did not match. Retry saving.');
      this.sequence=result.sequence;this.verifiedTick=result.verifiedTick;
      this.actions.splice(0,pending.count);this.pending=null;
      if(pending.finish)this.finished=result;
      return result;
    })();
    let result;
    try{result=await this.inFlight;}finally{this.inFlight=null;}
    // A final save must first acknowledge any earlier checkpoint whose exact
    // payload was retained after a connection error. Never change that retry.
    return finish&&!pending.finish?this.flush(endTick,{finish:true}):result;
  }
}
