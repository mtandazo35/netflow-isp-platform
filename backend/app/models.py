from datetime import datetime
from ipaddress import IPv4Address, IPv6Address

from pydantic import BaseModel, Field, model_validator


class FlowIn(BaseModel):
    event_time: datetime
    end_time: datetime
    exporter_ip: IPv4Address | IPv6Address
    source_ip: IPv4Address | IPv6Address
    destination_ip: IPv4Address | IPv6Address
    source_port: int = Field(ge=0, le=65535)
    destination_port: int = Field(ge=0, le=65535)
    protocol: int = Field(ge=0, le=255)
    bytes: int = Field(ge=0)
    packets: int = Field(ge=0)
    direction: str = Field(pattern="^(unknown|upload|download)$")
    subscriber_id: int = Field(default=0, ge=0)
    subscriber_name: str = ""
    plan_mbps: int = Field(default=0, ge=0)
    access_type: str = Field(default="unknown", pattern="^(unknown|pppoe|dhcp|static)$")
    domain: str = ""
    application: str = ""
    attribution_confidence: str = Field(default="unknown", pattern="^(unknown|low|medium|high)$")
    asn: int = Field(default=0, ge=0)
    country: str = Field(default="", max_length=2)

    @model_validator(mode="after")
    def validate_times(self):
        if self.end_time < self.event_time:
            raise ValueError("end_time must be equal to or after event_time")
        return self


class FlowBatch(BaseModel):
    flows: list[FlowIn] = Field(min_length=1, max_length=10_000)


class DNSAnswerIn(BaseModel):
    event_time: datetime
    client_ip: IPv4Address | IPv6Address
    domain: str = Field(min_length=1, max_length=253)
    answer_ip: IPv4Address | IPv6Address
    ttl: int = Field(ge=0, le=604_800)
    resolver: str = Field(default="unknown", max_length=64)


class DNSAnswerBatch(BaseModel):
    answers: list[DNSAnswerIn] = Field(min_length=1, max_length=10_000)
