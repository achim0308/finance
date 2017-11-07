from datetime import date

def newtonSolve(f, df, x0, absTol=1E-4, relTol=1E-4, itMax=50, damping=0.70):
    lastX = x0
    nextX = lastX + 10.0 * absTol
    it = 0
    while (abs(lastX - nextX) > absTol or abs(lastX - nextX) > relTol*abs(lastX)):
        it = it + 1
        if it > itMax:
            raise StopIteration('Exceed iteration count')
        newY = f(nextX)
        lastX = nextX
        if (nextX > 10.0 or nextX < -1.0):
            raise StopIteration('Diverging')
        try:
            nextX = lastX - damping * newY / df(nextX)
        except ZeroDivisionError:
            nextX = lastX + absTol
    return nextX
    
def solverF2(rate, cashflowList):
    d0 = cashflowList[0]['date']
    return sum([float(c['cashflow']) / (1 + rate)**((c['date'] - d0).days / 365.0) for c in cashflowList])

def solverDF2(rate, cashflowList):
    d0 = cashflowList[0]['date']
    return sum([-(c['date'] - d0).days/365.0 * float(c['cashflow']) / (1 + rate)**((c['date'] - d0).days / 365.0 + 1.0) for c in cashflowList])

def callSolver2(cashflowList):
    if not cashflowList:
        raise RuntimeError('Empty list')
    r0 = 0
    f = lambda r: solverF2(r, cashflowList)
    df = lambda r: solverDF2(r, cashflowList)

    try:
        r = newtonSolve(f, df, r0)
    except StopIteration:
        raise RuntimeError('Iteration limit exceeded')
        
    return float(r)*100.0

class Solver():
    # solver to determine rate of return of given date-cashflow tuples
    
    def __init__(self):
        self.cashflowList = {}
        self.date0 = date(2000,1,1)

    def __str__(self):
        s = ""
        for d in self.cashflowList:
            s += str(d)  + ": " + str(self.cashflowList[d]) + "\n"
        return s
        
    def addCashflow(self,cashflow, date):
        if len(self.cashflowList) == 0:
            self.date0 = date
        diffDate = (date - self.date0).days
        if not diffDate in self.cashflowList:
            self.cashflowList[diffDate] = float(cashflow)
        else:
            self.cashflowList[diffDate] = self.cashflowList[diffDate] + float(cashflow)
    def calcRateOfReturn(self):
        if not self.cashflowList:
            raise RuntimeError('Empty list')
        r0 = 0.0
        f = lambda r: self._solverF(r)
        df = lambda r: self._solverDF(r)
        try:
            r = self._newtonSolve(f=f, df=df, x0=r0)
        except StopIteration as e:
            print(e)
            raise RuntimeError('Iteration limit exceeded')
        
        return float(r)*100.0        

	# private functions    
    def _solverF(self, rate):
        return sum([cashflow / (1 + rate)**(diffDays / 365.0) \
                    for diffDays, cashflow in self.cashflowList.items()])

    def _solverDF(self, rate):
        return sum([-diffDays/365.0 * cashflow / (1 + rate)**(diffDays / 365.0 + 1.0)
                    for diffDays, cashflow in self.cashflowList.items()])
    
    def _newtonSolve(self, f, df, x0, absTol=1E-4, relTol=1E-4, itMax=50, damping=0.70):
        lastX = x0
        nextX = lastX + 10.0 * absTol
        it = 0
        while (abs(lastX - nextX) > absTol or abs(lastX - nextX) > relTol*abs(lastX)):
            it = it + 1
            if it > itMax:
                raise StopIteration('Exceed iteration count')
            newY = f(nextX)
            lastX = nextX

            try:
                nextX = lastX - damping * newY / df(nextX)
            except ZeroDivisionError:
                nextX = lastX + absTol
            if (nextX > 10.0 or nextX < -1.0):
                raise StopIteration('Diverging')
        return nextX
