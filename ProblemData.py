import networkx as nx
import random
import math
import csv
from tools import pairwise

class ProblemData(object):
    """description of class"""
    __slots__ = ['commodities', 'network', 'position', 'capacities', 'fixed_cost', 'var_cost', 'solution', 'fixed_paths']

    def __init__(self, commodities, network, position=None, capacities={}, fixed_cost={}, var_cost={}, solution=None, fixed_paths=None):
        self.commodities = commodities
        self.network = network
        self.position = position
        self.capacities = capacities
        self.fixed_cost = fixed_cost
        self.var_cost = var_cost
        self.solution = solution
        self.fixed_paths = fixed_paths


    ## Scales the time horizon (network and commodities) for this problem
    def scale(self, scale):
        for k,c in enumerate(self.commodities):
            c['a'] = (c['a'][0], int(math.ceil(c['a'][1]*scale)))
            c['b'] = (c['b'][0], int(math.ceil(c['b'][1]*scale)))

        for a, destinations in self.network.items():
            for b, transit_time in destinations.items():
                destinations[b] = int(math.ceil(transit_time * scale))

        return self


    ## Pessimistically rounds time as if using coarser time discretization, assumes data is in 1 minute discretization
    def pessimistic_round(self, minutes):
        # copy costs from transit to fix rounding issues
        copy_cost = len(self.fixed_cost) == 0

        for k,c in enumerate(self.commodities):
            c['a'] = (c['a'][0], int(math.ceil(c['a'][1]/float(minutes))))   # early up
            c['b'] = (c['b'][0], int(math.floor(c['b'][1]/float(minutes))))  # late down

        # transit times up
        for a, destinations in self.network.items():
            for b, transit_time in destinations.items():
                destinations[b] = int(math.ceil(transit_time/float(minutes)))

                if copy_cost:
                    self.fixed_cost[(a,b)] = transit_time

        return self

    ## Optimistically rounds time as if using coarser time discretization, assumes data is in 1 minute discretization
    def optimistic_round(self, minutes):
        # copy costs from transit to fix rounding issues
        copy_cost = len(self.fixed_cost) == 0

        for k,c in enumerate(self.commodities):
            c['a'] = (c['a'][0], int(math.floor(c['a'][1]/float(minutes))))   # early down
            c['b'] = (c['b'][0], int(math.ceil(c['b'][1]/float(minutes))))  # late up

        # transit times down
        for a, destinations in self.network.items():
            for b, transit_time in destinations.items():
                destinations[b] = int(math.floor(transit_time/float(minutes)))

                if copy_cost:
                    self.fixed_cost[(a,b)] = transit_time

        return self

    ## Simply rounds time as if using coarser time discretization, assumes data is in 1 minute discretization
    def simple_round(self, minutes):
        # copy costs from transit to fix rounding issues
        copy_cost = len(self.fixed_cost) == 0

        for k,c in enumerate(self.commodities):
            c['a'] = (c['a'][0], int(round(c['a'][1]/float(minutes))))   # early
            c['b'] = (c['b'][0], int(round(c['b'][1]/float(minutes))))  # late

        # transit times
        for a, destinations in self.network.items():
            for b, transit_time in destinations.items():
                destinations[b] = int(round(transit_time/float(minutes)))

                if copy_cost:
                    self.fixed_cost[(a,b)] = transit_time

        return self


    ## Randomizes a previous problem
    def randomize(self, commodity_number=None, commodity_range=(0,10), quantity_range=(0, 2), start_range=(0, 10), origin_set=[], dest_set=[], scope=None, scope_range=(1, 4)):
        p = ProblemData.random_problem(self.network, commodity_number, commodity_range, quantity_range, start_range, origin_set, dest_set, scope, scope_range)
        p.position = self.position
        return p

    ##
    ## Load problem data from common format (Mike Hewitt)
    ##
    @classmethod
    def read_file(cls, filename):
        commodities = []
        network = {}
        positions = []
        capacities = {}
        fixed_cost = {}
        var_cost = {}

        with open(filename, "r") as file:
            while not file.readline().startswith("NODES"):
                pass

            line = file.readline()

            if line.startswith("I"):
                line = file.readline() # skip header

            # read positions
            while not line.startswith("ARCS"):
                tmp = line.split(',')

                if not tmp[2].startswith('-') and not tmp[3].startswith('-'):
                    positions.append([float(tmp[2]), float(tmp[3])])

                line = file.readline()

            line = file.readline()

            if line.startswith("I"):
                line = file.readline() # skip header

            while not line.startswith("COMMODITIES"):
                tmp = line.split(',')

                if int(tmp[1]) not in network:
                    network[int(tmp[1])] = {}

                network[int(tmp[1])][int(tmp[2])] = float(tmp[6])
                
                if float(tmp[5]) >= 0:  # ignore capacities of -1
                    capacities[(int(tmp[1]),int(tmp[2]))] = float(tmp[5])

                fixed_cost[(int(tmp[1]),int(tmp[2]))] = float(tmp[4])
                var_cost[(int(tmp[1]),int(tmp[2]))] = float(tmp[3])

                line = file.readline()

            line = file.readline()

            if line.startswith("I"):
                line = file.readline() # skip header

            while len(line) > 0 and not (line.startswith('horizon') or line.startswith("cost")):
                tmp = line.split(',')
                commodities.append({'a': (int(tmp[1]), float(tmp[4])), 'b': (int(tmp[2]), float(tmp[5])), 'q': float(tmp[3])})
                line = file.readline()

            ## load solution
            solution_cost = None
            solution_paths = []
            solution_cons = []

            if len(line) > 0 and line.startswith('horizon'):
                line = file.readline()

            if len(line) > 0 and line.startswith('cost'):
                solution_cost = float(line.split('=')[1])
                line = file.readline()  # PATHS
                line = file.readline()

                if line.startswith("Index"):
                    line = file.readline() # skip header

                # load solution paths
                while len(line) > 0 and not line.startswith("CONS"):
                    tmp = line.split(',')
                    solution_paths.append(map(int, tmp[1:]))
                    line = file.readline()

                line = file.readline() # CONS
            
                if line.startswith("Origin"):
                    line = file.readline() # skip header

                while len(line) > 0:
                    tmp = map(int, line.split(','))
                    solution_cons.append((tuple(tmp[:2]), frozenset(tmp[2:])))
                    line = file.readline()

            return ProblemData(commodities, network, positions if positions else None, capacities, fixed_cost, [var_cost]*len(commodities), (solution_cost, solution_paths, solution_cons) if solution_cost != None else None)

    ##
    ## Save problem data in common format (Mike Hewitt)
    ##
    def save(self, filename, solution=None):
        graph = nx.DiGraph()

        for a, destinations in self.network.items():
            for b, transit_time in destinations.items():
                graph.add_edge(a, b, weight=transit_time, cost=transit_time)

        with open(filename, "w") as file:
            file.write("NODES," + str(len(graph.nodes())) + '\n')
            file.write("INDEX,Name,X-coordinate,Y-coordinate\n")

            try:
                position = self.position if self.position else nx.pygraphviz_layout(graph, prog='neato')
        
                for n in graph.nodes():
                    file.write("{0},{1},{2},{3}\n".format(n, n, position[n][0], position[n][1]))
            except:
                # don't write position                
                for n in graph.nodes():
                    file.write("{0},{1},-,-\n".format(n, n))

            file.write("ARCS," + str(len(graph.edges())) + '\n')
            file.write("Index,Origin,Destination,Variable Cost,Fixed Cost,Capacity,Travel time\n")

            for i, (a,b) in enumerate(graph.edges()):
                file.write("{0},{1},{2},{3},{4},{5},{6}\n".format(i, a, b, self.var_cost[(a,b)] if (a,b) in self.var_cost else 0, self.fixed_cost[(a,b)] if (a,b) in self.fixed_cost else self.network[a][b], self.capacities[(a,b)] if (a,b) in self.capacities else 1, self.network[a][b]))

            file.write("COMMODITIES," + str(len(self.commodities)) + '\n')
            file.write("Index,Origin,Destination,Demand/Size,Earliest available time,Latest delivery time\n")

            for k,c in enumerate(self.commodities):
                file.write("{0},{1},{2},{3},{4},{5}\n".format(k, c['a'][0], c['b'][0], c['q'], c['a'][1], c['b'][1]))

            file.write("horizon={0}\n".format(max(c['b'][1] for c in self.commodities) - min(c['a'][1] for c in self.commodities)))

            if solution != None:
                file.write("cost={0}\n".format(solution[0]))

                file.write("PATHS,{0}\n".format(len(solution[1])))
                file.write("Index,Nodes\n")

                for k,p in enumerate(solution[1]):
                    file.write("{0},{1}\n".format(k,",".join(map(str,p))))

                file.write("CONSOLIDATIONS,{0}\n".format(len(solution[2])))
                file.write("Origin,Destination,Commodities\n")

                for (n1,n2),K in solution[2]:
                    file.write("{0},{1},{2}\n".format(n1,n2,",".join(map(str,K))))


    ##
    ## Creates a randomly generated problem
    ##
    ## commodity_number: number of commodities to generate (default chooses random number in commodity_range)
    ## commodity_range: integer (lower, upper]
    ## quantity_range: rational (lower, upper]
    ## start_range: integer [lower, upper)
    ##
    ## scope: scale of time window ~ scope * shortest_path[origin][destination]
    ## scope_range: rational > 1 (lower, upper]
    ##
    ## origin_set: the set of available origins to choose from
    ## dest_set: the set of available destinations to choose from
    ##
    @classmethod
    def random_problem(cls, network, commodity_number=None, commodity_range=(0,10), quantity_range=(0, 2), start_range=(0, 10), origin_set=[], dest_set=[], scope=None, scope_range=(1, 4)):
        if commodity_number == None:
            commodity_number = commodity_range[1] - random.randrange(commodity_range[0], commodity_range[1])

        commodities = []

        # build graph
        graph = nx.DiGraph()

        for a, destinations in network.items():
            for b, transit_time in destinations.items():
                graph.add_edge(a, b, weight=transit_time, cost=transit_time)

        shortest_paths = nx.shortest_path_length(graph, weight='weight')

        # generate commodities
        for k in range(commodity_number):
            # choose valid origin/destination pair
            origin, dest = random.choice(origin_set or graph.nodes()), random.choice(dest_set or graph.nodes())

            while origin == dest or dest not in shortest_paths[origin]:
                origin, dest = random.choice(origin_set or graph.nodes()), random.choice(dest_set or graph.nodes())

            # choose valid time window
            origin_time = random.randrange(start_range[0], start_range[1])
            dest_time = origin_time + int(shortest_paths[origin][dest] * (scope if scope != None else random.uniform(scope_range[0], scope_range[1])))
            
            commodities.append({'a': (origin, origin_time), 'b': (dest, dest_time), 'q': max(0.01, round(quantity_range[1] - random.uniform(quantity_range[0], quantity_range[1]), 2))})

        return ProblemData(commodities, network)


    ##
    ## Load tsp problem data from tw file.  Note this works, but is TERRIBLY slow
    ##
    @classmethod
    def read_tsp(cls, filename):
        commodities = []
        network = {}
        positions = []
        capacities = {}
        fixed_cost = {}
        var_cost = {}

        with open(filename, "r") as file:
            nodes = int(file.readline())

            # complete graph
            network = {i: {j: float(t) for j,t in enumerate(filter(None, file.readline().rstrip().split(' '))) if j != i} for i in range(nodes)}

            for a,G in network.items():
                for b,v in G.items():
                    if v == 0:
                        fixed_cost[a,b] = 1000

            M = float(filter(None, file.readline().rstrip().split(' '))[1])

            for i in range(nodes - 1):
                t = filter(None, file.readline().rstrip().split(' '))

                commodities.append({'a': (i+1, float(t[0])), 'b': (0, M), 'q': 1/float(nodes+1)})
                commodities.append({'a': (0, 0), 'b': (i+1,float(t[1])), 'q': 1/float(nodes+1)})

            return ProblemData(commodities, network, None, capacities, fixed_cost, var_cost, None)


    ##
    ## Load instance from DDD-arc paper
    ##
    @classmethod
    def read_directory(cls, directory):
        commodities = []
        network = {}
        positions = []
        capacities = {}
        fixed_cost = {}
        var_cost = {}
        fixed_paths = []

        nodes = {}

        with open(directory + '/nodes.csv') as csvfile:
            reader = csv.reader(csvfile)
            next(reader) # skip header

            for row in reader:
                nodes[row[0]] = len(nodes)

        commodity_var_cost = {}
        commodity_var_cost_network = []
        commodity_map = {}

        # id,origin,destination,demand,release_time,deadline
        with open(directory + '/commodities.csv') as csvfile:
            reader = csv.reader(csvfile)
            next(reader) # skip header

            for row in reader:
                origin,dest = nodes[row[1]], nodes[row[2]]
                commodities.append({'a': (origin, float(row[4])), 'b': (dest, float(row[5])), 'q': float(row[3])})
                commodity_map[row[0]] = len(commodity_map)
                commodity_var_cost_network.append({})

                # load fixed paths
                if len(row) > 7:
                    fixed_paths.append(list(pairwise([nodes[n.strip(" '")] for n in row[7].strip('[]').split(',')])))

        #commodity,arcs
        with open(directory + '/variable_costs.csv') as csvfile:
            reader = csv.reader(csvfile)
            row = next(reader) # read header
            arc_map = {f: i for i,f in enumerate(row) if f != 'commodity'} 

            for row in reader:
                commodity_var_cost[commodity_map[row[0]]] = {k: row[v] for k,v in arc_map.items()}

        # id,origin,destination,transit_time,capacity,fixed_cost,variable_cost
        with open(directory + '/arcs.csv') as csvfile:
            reader = csv.reader(csvfile)
            next(reader) # skip header

            for row in reader:
                origin,dest = nodes[row[1]], nodes[row[2]]

                if origin not in network:
                    network[origin] = {}

                network[origin][dest] = float(row[3])
                
                if float(row[4]) >= 0:  # ignore capacities of -1
                    capacities[(origin,dest)] = float(row[4])

                fixed_cost[(origin,dest)] = float(row[5])

                if row[6] != '': # ignore empty variable costs
                    var_cost[(origin,dest)] = float(row[6])

                for k in range(len(commodities)):
                    commodity_var_cost_network[k][origin,dest] = float(commodity_var_cost[k][row[0]])
    
        return ProblemData(commodities, network, None, capacities, fixed_cost, commodity_var_cost_network, None, fixed_paths)