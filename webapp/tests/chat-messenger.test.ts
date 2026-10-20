import test from 'node:test';
import assert from 'node:assert/strict';
import {sentByThisBot} from '../src/lib/chat-messenger';
import type {GroupMessage} from '../src/lib/group-view';

test('only the connected bot or confirmed local send appears on the outgoing side',()=>{
 const message={is_bot:true,sender_username:'Videl0Bot'} as GroupMessage;
 assert.equal(sentByThisBot(message,'@videl0bot'),true);
 assert.equal(sentByThisBot({...message,sender_username:'OtherBot'},'Videl0Bot'),false);
 assert.equal(sentByThisBot({...message,is_bot:false},'Videl0Bot'),false);
 assert.equal(sentByThisBot({...message,sender_username:''},'Videl0Bot'),false);
 assert.equal(sentByThisBot({...message,ephemeral:true,sender_username:''},'Videl0Bot'),true);
});
