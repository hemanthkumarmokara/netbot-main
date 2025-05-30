
def is_routing_possible(source_ip: str, dest_ip: str) -> str:
    try:
       
        source_first = int(source_ip.split('.')[0])
        dest_first = int(dest_ip.split('.')[0])
        
        if 1 <= source_first <= 5 and 1 <= dest_first <= 5:
            return "Yes, routing possible."
        elif 6 <= source_first <= 9 and 6 <= dest_first <= 9:
            return "No, routing is not possible."
        else:
            return "Routing information is ambiguous based on provided IPs."
    except Exception as e:
        return f"Error determining routing: {e}"
