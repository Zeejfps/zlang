using LexerModule;
using LLVMSharp.Interop;
using ParserModule;
using ParserModule.Nodes;

namespace CodeGenModule;

public sealed class ExpressionVisitor : IExpressionNodeVisitor
{
    private readonly Dictionary<string, LLVMValueRef> _scope;
    private readonly LLVMBuilderRef _builder;

    public ExpressionVisitor(Dictionary<string, LLVMValueRef> scope, LLVMBuilderRef builder)
    {
        _scope = scope;
        _builder = builder;
    }

    public LLVMValueRef Result { get; private set; }
    
    public void VisitLiteralInteger(LiteralIntegerExpressionNode node)
    {
        Result = LLVMValueRef.CreateConstInt(LLVMTypeRef.Int32, (ulong)node.Value);
    }

    public void VisitLiteralBool(LiteralBoolExpressionNode node)
    {
        Result = LLVMValueRef.CreateConstInt(LLVMTypeRef.Int1, (ulong)(node.Value ? 1 : 0));       
    }

    public void VisitBinary(BinaryExpressionNode node)
    {
        node.Left.Accept(this);
        var left = Result;
        
        node.Right.Accept(this);
        var right = Result;
        
        if (node.Op.Kind == TokenKind.SymbolPlus)
        {
            Result = _builder.BuildAdd(left, right);
        }
        else if (node.Op.Kind == TokenKind.SymbolMinus)
        {
            Result = _builder.BuildSub(left, right);
        }
        else if (node.Op.Kind == TokenKind.SymbolLessThan)
        {
            Result = _builder.BuildICmp(LLVMIntPredicate.LLVMIntSLT, left, right);
        }
        else if (node.Op.Kind == TokenKind.SymbolLessThanEquals)
        {
            Result = _builder.BuildICmp(LLVMIntPredicate.LLVMIntSLE, left, right);
        }
        else if (node.Op.Kind == TokenKind.SymbolGreaterThan)
        {
            Result = _builder.BuildICmp(LLVMIntPredicate.LLVMIntSGT, left, right);
        }
        else if (node.Op.Kind == TokenKind.SymbolGreaterThanEquals)
        {
            Result = _builder.BuildICmp(LLVMIntPredicate.LLVMIntSGE, left, right);
        }
        else
        {
            throw new Exception("Unknown binary operator");       
        }
    }

    public void VisitUnary(UnaryExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitIdentifier(IdentifierExpressionNode node)
    {
        Result = _scope[node.Name];
    }
    
}