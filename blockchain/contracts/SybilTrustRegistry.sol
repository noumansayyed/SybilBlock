// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
contract SybilTrustRegistry {
    address public owner;
    struct Record { uint8 trustScore; uint64 updatedAt; string modelVersion; bool exists; }
    mapping(bytes32 => Record) private records;
    event TrustScoreUpdated(bytes32 indexed accountId,uint8 trustScore,uint64 updatedAt,string modelVersion);
    modifier onlyOwner(){require(msg.sender==owner,"Not authorized");_;}
    constructor(){owner=msg.sender;}
    function updateTrustScore(bytes32 accountId,uint8 score,string calldata modelVersion) external onlyOwner {
        require(score<=100,"Invalid score");require(accountId!=bytes32(0),"Invalid account ID");
        uint64 ts=uint64(block.timestamp);records[accountId]=Record(score,ts,modelVersion,true);
        emit TrustScoreUpdated(accountId,score,ts,modelVersion);
    }
    function getAccountRecord(bytes32 accountId) external view returns(uint8,uint64,string memory,bool){
        Record storage r=records[accountId];return(r.trustScore,r.updatedAt,r.modelVersion,r.exists);
    }
}
